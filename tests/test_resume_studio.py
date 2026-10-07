import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import resume_studio as studio
import server


def profile():
    return studio.validate_profile({'name':'Alex Example','contacts':['alex@example.com'],
        'sections':[{'title':'Experience','kind':'experience','entries':[
            {'title':'Engineer | Java','subtitle':'Example Labs','dates':'2022 - Present','bullets':[
                'Reduced underwriting time by 85% using Python APIs.',
                'Processed 150+ submissions/day with Kafka on AKS.',
                'Estimated 30% reduction in MTTR using an LLM.'],
             'groups':[{'heading':'Deployment project','bullets':['Built Docker images for Python services.']}]}]},
        {'title':'Technical Skills','kind':'skills','entries':[{'title':'Languages','subtitle':'SQL','bullets':[]}]}]})


def job(**overrides):
    return dict({'id':'demo:1','company':'Example Company','title':'Backend Engineer',
                 'status_source':'active','fit_band':'strong','full_description':
                 'We require Python APIs, Kafka, Kubernetes and PostgreSQL. JavaScript is preferred. Build Docker services with an LLM. Review production incidents.'},**overrides)


class ResumeTests(unittest.TestCase):
    def test_exact_metrics_qualifiers_and_context(self):
        p=profile();r=studio.generate(p,job(),4)
        for s in r['audit']['selected_statements']:
            self.assertIn(s['text'],[e['text'] for e in studio.evidence(p)])
        self.assertIn('Estimated 30% reduction',r['resume_text'])
        self.assertIn('150+ submissions/day',r['resume_text'])
        self.assertIn('Example Labs',r['cover_letter_text'])
        self.assertNotIn('PostgreSQL',r['resume_text'])
        self.assertIn('Deployment project',r['resume_text'])
        self.assertIn('group.0.0',[s['id'].split('.',2)[-1] for s in r['audit']['selected_statements']])

    def test_gap_distinguishes_skills_and_evidence(self):
        a=studio.analyze(profile(),job())
        self.assertIn('PostgreSQL',a['missing']);self.assertIn('JavaScript',a['missing'])
        self.assertNotIn('Kubernetes',a['missing'])
        a=studio.analyze(profile(),job(full_description='SQL Java are required. '+'Relevant software development skills. '*3))
        self.assertEqual(set(a['listed_only']),{'SQL','Java'})
        self.assertEqual(studio.topics('go to the office'),'set' if False else set())

    def test_summary_only_cannot_generate(self):
        j=job(full_description='',requirements='Python Kafka')
        self.assertEqual(studio.analyze(profile(),j)['coverage'],'summary_only')
        with self.assertRaises(ValueError):studio.generate(profile(),j)

    def test_tex_escapes_every_untrusted_field(self):
        p=profile();p['name']=r'Alex \input{secrets} & 20% #_$^~'
        r=studio.generate(p,job())
        self.assertNotIn(r'\input{secrets}',r['resume_tex'])
        self.assertIn(r'\textbackslash{}input\{secrets\}',r['resume_tex'])
        self.assertIn(r'85\%',r['resume_tex'])

    def test_supplied_template_emphasis_and_safe_contact_links(self):
        p=profile();p['sections'][0]['entries'][0]['emphasis']=['85%']
        p['contact_links']={'alex@example.com':'mailto:alex@example.com'}
        p=studio.validate_profile(p);r=studio.generate(p,job())
        self.assertIn(r'\documentclass[letterpaper,11pt]',r['resume_tex'])
        self.assertIn(r'\resumeSubheading{',r['resume_tex'])
        self.assertIn(r'\textbf{85\%}',r['resume_tex'])
        self.assertIn(r'\href{mailto:alex@example.com}',r['resume_tex'])
        self.assertIn('85%',r['resume_text'])
        p['contact_links']['alex@example.com']='javascript:alert(1)'
        with self.assertRaises(ValueError):studio.validate_profile(p)

    def test_gap_filters_and_profile_changes(self):
        jobs=[job(),job(id='closed',status_source='not_listed'),job(id='passed',application_status='Passed'),job(id='incomplete',full_description='',requirements='Python Kafka')]
        r=studio.gap_report(profile(),jobs)
        self.assertEqual(r['jobs_scanned'],4);self.assertEqual(r['prospects'],2);self.assertEqual(r['full_jd_count'],1)
        p=profile();p['full_details']='Used PostgreSQL in a personal project.'
        changed=studio.analyze(p,job());self.assertNotEqual(changed['profile_hash'],r['profile_hash'])
        self.assertNotIn('PostgreSQL',changed['missing']);self.assertIn('PostgreSQL',changed['listed_only'])

    def test_validation_and_backup(self):
        for bad in ({}, {'name':'Alex','sections':[None]}, {'name':'Alex','sections':[{'kind':'experience','title':'Work','entries':[None]}]}):
            with self.assertRaises(ValueError):studio.validate_profile(bad)
        with tempfile.TemporaryDirectory() as d:
            p=profile();studio.save_profile(d,p);p['full_details']='More context';studio.save_profile(d,p)
            self.assertEqual(len(list(Path(d,'backups').glob('*.json'))),1)
            self.assertEqual(studio.load_profile(d)['full_details'],'More context')

    def test_selection_changes_without_mutating_profile(self):
        p=profile();before=copy.deepcopy(p)
        r=studio.generate(p,job(full_description='Kafka streaming on Kubernetes. '+'Event processing and operational delivery. '*3),1)
        self.assertIn('150+ submissions/day',r['resume_text']);self.assertNotIn('85%',r['resume_text'])
        self.assertEqual(before,p)


class ResumeHTTPTests(unittest.TestCase):
    def test_save_generate_gaps_jd_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as d, patch.object(server,'DATA',Path(d)),patch.object(server,'DB_PATH',Path(d)/'test.sqlite'):
            server.initialize()
            j=job()
            with server.connect() as db:db.execute('INSERT INTO jobs VALUES (?,?,?)',(j['id'],'demo',json.dumps(j)))
            class Quiet(server.Handler):
                def log_message(self,*args):pass
            http=server.ThreadingHTTPServer(('127.0.0.1',0),Quiet)
            worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
            def request(path,body=None):
                req=Request(f'http://127.0.0.1:{http.server_port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
                with urlopen(req,timeout=10) as response:return json.load(response)
            try:
                self.assertIsNone(request('/api/resume/profile')['profile'])
                request('/api/resume/profile',{'profile':profile()})
                generated=request('/api/resume/generate',{'job_id':j['id']})
                self.assertIn('resume_tex',generated)
                pdf_body=dict(generated['pdf_request'],kind='resume')
                with patch.object(studio,'compile_pdf',return_value=b'%PDF-1.7\nfixture') as compile_mock:
                    req=Request(f'http://127.0.0.1:{http.server_port}/api/resume/pdf',data=json.dumps(pdf_body).encode(),headers={'Content-Type':'application/json'})
                    with urlopen(req) as response:
                        self.assertEqual(response.headers['Content-Type'],'application/pdf')
                        self.assertIn('resume.pdf',response.headers['Content-Disposition'])
                        self.assertTrue(response.read().startswith(b'%PDF-'))
                    self.assertEqual(compile_mock.call_args.args[0],generated['resume_tex'])
                with patch.object(studio,'compile_pdf',side_effect=RuntimeError('Compiler unavailable')):
                    with self.assertRaises(HTTPError) as e:request('/api/resume/pdf',pdf_body)
                    self.assertEqual(e.exception.code,503);e.exception.close()
                with self.assertRaises(HTTPError) as e:request('/api/resume/pdf',dict(pdf_body,profile_hash='stale'))
                self.assertEqual(e.exception.code,409);e.exception.close()
                with self.assertRaises(HTTPError) as e:request('/api/resume/pdf',dict(pdf_body,kind='../file'))
                self.assertEqual(e.exception.code,400);e.exception.close()
                self.assertEqual(request('/api/resume/gaps')['jobs_scanned'],1)
                request('/api/resume/jd',{'job_id':j['id'],'full_description':j['full_description']+' Updated.'})
                for body in ({'job_id':'missing'},{'job_id':j['id'],'max_bullets':True}):
                    with self.assertRaises(HTTPError) as e:request('/api/resume/generate',body)
                    self.assertEqual(e.exception.code,400);e.exception.close()
                self.assertEqual(request('/api/state')['jobs'][0]['full_description'],j['full_description']+' Updated.')
            finally:http.shutdown();http.server_close();worker.join()


if __name__=='__main__':unittest.main()
