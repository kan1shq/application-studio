import importlib.util, json, tempfile, unittest, threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('server',ROOT/'server.py'); app=importlib.util.module_from_spec(spec); spec.loader.exec_module(app)

class RefreshPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.old_data,self.old_db=app.DATA,app.DB_PATH
        app.DATA=Path(self.temp.name); app.DB_PATH=app.DATA/'test.sqlite'; app.initialize()
        (app.DATA/'plan.json').write_text(json.dumps({'days':[{'day':n} for n in range(1,141)]}),encoding='utf-8')
        self.source={'id':'ashby:example','provider':'ashby','board':'example','company':'Example'}
        self.job={'id':'ashby:example:1','source_id':'ashby:example','title':'Backend Engineer','location':'Berlin','status_source':'active','verified_at':'2026-01-01T00:00:00Z','reviewed':True,'fit_band':'strong','fit_reasons':'Reviewed','gaps':'Database depth'}
        with app.connect() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?)',(self.job['id'],self.source['id'],json.dumps(self.job)))
            db.execute('INSERT INTO job_state VALUES (?,?,?,?)',(self.job['id'],'Applied','Referral already sent','2026-01-02'))
    def tearDown(self):
        app.DATA,self.old_data=self.old_data,app.DATA;app.DB_PATH=self.old_db;self.temp.cleanup()
    def feed_job(self,external='1',title='Backend Engineer',description='Python API developer with 3+ years experience'):
        return {'external_id':external,'title':title,'location':'Berlin','apply_url':'https://example.com/apply','source_url':'https://example.com/job','description':description,'posted_at':None,'salary_feed':'Not published'}
    def get_job(self,jid='ashby:example:1'):
        with app.connect() as db:return json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(jid,)).fetchone()['payload'])
    def test_success_keeps_notes_and_marks_only_absent_ids(self):
        with patch.object(app,'fetch_board',return_value=([self.feed_job('2')],'https://example.com/feed')): result=app.refresh_source(self.source)
        self.assertTrue(result['ok']);self.assertEqual(self.get_job()['status_source'],'not_listed');self.assertEqual(self.get_job('ashby:example:2')['status_source'],'active')
        with app.connect() as db:self.assertEqual(db.execute('SELECT notes,status FROM job_state').fetchone()['status'],'Applied')
    def test_network_failure_does_not_close_or_refresh_timestamp(self):
        with patch.object(app,'fetch_board',side_effect=TimeoutError('temporary timeout')): result=app.refresh_source(self.source)
        self.assertFalse(result['ok']);self.assertEqual(self.get_job()['status_source'],'active');self.assertEqual(self.get_job()['verified_at'],self.job['verified_at'])
    def test_repeated_success_is_idempotent_and_preserves_review(self):
        with patch.object(app,'fetch_board',return_value=([self.feed_job()],'https://example.com/feed')):
            app.refresh_source(self.source);app.refresh_source(self.source)
        self.assertTrue(self.get_job()['reviewed'])
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)
    def test_changed_requirements_need_new_review(self):
        with patch.object(app,'fetch_board',return_value=([self.feed_job()],'https://example.com/feed')):app.refresh_source(self.source)
        with patch.object(app,'fetch_board',return_value=([self.feed_job(description='Java API architect with 8+ years experience')],'https://example.com/feed')):app.refresh_source(self.source)
        self.assertFalse(self.get_job()['reviewed']);self.assertEqual(self.get_job()['fit_band'],'Needs review')
    def test_nonmatching_new_roles_excluded(self):
        with patch.object(app,'fetch_board',return_value=([self.feed_job('2','Engineering Manager'),self.feed_job('3','Backend Engineer')],'https://example.com/feed')):app.refresh_source(self.source)
        with app.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM jobs WHERE id=?',('ashby:example:2',)).fetchone())
        self.assertEqual(self.get_job('ashby:example:3')['fit_band'],'Needs review')
    def test_geography_does_not_call_uk_eu(self):
        self.assertEqual(app.region_of('Stuttgart')[0],'EU');self.assertEqual(app.region_of('Singapore')[0],'Asia');self.assertNotEqual(app.region_of('London, United Kingdom')[0],'EU');self.assertEqual(app.region_of('Bangalore HQ')[2],2)
    def test_http_save_reload_and_validation(self):
        class QuietHandler(app.Handler):
            def log_message(self,*args): pass
        http=app.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        base=f'http://127.0.0.1:{http.server_port}'
        def request(path,body=None,origin=None):
            headers={'Content-Type':'application/json'}
            if origin:headers['Origin']=origin
            req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            with urlopen(req,timeout=5) as response:return json.load(response)
        try:
            request('/api/job-state',{'id':self.job['id'],'status':'Interviewing','notes':'Call scheduled'})
            request('/api/prep-state',{'day':3,'state':{'tasks':[0,2],'notes':'Continue SQL','minimum_done':True,'energy':'minimum'}})
            app.initialize()
            result=request('/api/state')
            self.assertEqual(result['jobs'][0]['application_status'],'Interviewing')
            self.assertEqual(result['prep_state']['3']['tasks'],[0,2])
            self.assertEqual(result['prep_state']['3']['notes'],'Continue SQL')
            request('/api/prep-state',{'day':140,'state':{'tasks':[0,2],'notes':'Serving boundary measured','energy':'standard'}})
            self.assertEqual(request('/api/state')['prep_state']['140']['notes'],'Serving boundary measured')
            self.assertEqual(request('/api/state')['prep_state']['3']['notes'],'Continue SQL')
            for bad_day in [71.0,True,141]:
                with self.assertRaises(HTTPError) as invalid_extension:request('/api/prep-state',{'day':bad_day,'state':{}})
                self.assertEqual(invalid_extension.exception.code,400)
                invalid_extension.exception.close()
            with self.assertRaises(HTTPError) as invalid:request('/api/prep-state',{'day':0,'state':{}})
            self.assertEqual(invalid.exception.code,400)
            invalid.exception.close()
            with self.assertRaises(HTTPError) as forbidden:request('/api/job-state',{'id':self.job['id'],'status':'Rejected'},'https://unrelated.example')
            self.assertEqual(forbidden.exception.code,403)
            forbidden.exception.close()
            self.assertEqual(request('/api/state')['jobs'][0]['application_status'],'Interviewing')
        finally:
            http.shutdown();http.server_close();worker.join(timeout=3)

class PlanIntegrityTests(unittest.TestCase):
    def test_extended_curriculum_preserves_interview_targets(self):
        plan=json.loads((ROOT/'data/plan.json').read_text(encoding='utf-8'))
        self.assertEqual(len(plan['projects']),15)
        self.assertEqual(len(plan['weeks']),20)
        self.assertEqual(len({p['id'] for p in plan['projects']}),15)
        questions=plan['interview_curriculum']['questions']
        self.assertEqual(len(questions),80)
        self.assertEqual(len({q['id'] for q in questions}),80)
        for week in plan['weeks']:
            self.assertEqual(len(week['questions']),8 if week['week']<=10 else 0)
            self.assertEqual(len(week['system_topics']),5)
            self.assertEqual(len(week['lessons']),5)
            days=[d for d in plan['days'] if d['week']==week['week']]
            self.assertEqual(len(days),7)
            self.assertEqual([d['session_kind'] for d in days[-2:]],['Weekend build','Weekend verification'])
        self.assertIn('2023-04-01',plan['interview_curriculum']['company_overlay']['freshness'])
    def test_all_140_days_are_actionable_and_bounded(self):
        plan=json.loads((ROOT/'data/plan.json').read_text(encoding='utf-8'))
        self.assertEqual([d['day'] for d in plan['days']],list(range(1,141)))
        for d in plan['days']:
            self.assertTrue(d['minimum_action']);self.assertTrue(d['deliverable']);self.assertTrue(d['resources'])
            self.assertGreater(len(d['core_tasks']),1)
            self.assertLessEqual(sum(t['minutes'] for t in d['core_tasks']),180)
            self.assertTrue(all(t['done_when'] for t in d['core_tasks']))
        for week in range(1,21):
            self.assertEqual(sum(t['minutes'] for d in plan['days'] if d['week']==week for t in d['core_tasks']),21*60)

    def test_library_references_and_modern_project_boundaries(self):
        plan=json.loads((ROOT/'data/plan.json').read_text(encoding='utf-8'))
        library=plan['learning_library']; ids={r['id'] for r in library['resources']}
        self.assertEqual(len(ids),len(library['resources']))
        for strand in library['strands']:
            self.assertTrue(set(strand['resource_ids'])<=ids,strand['title'])
        self.assertEqual([c['day'] for c in library['checkpoints']],[42,56,70,140])
        builds=' '.join(p['build'] for p in plan['projects']).lower()
        for obsolete in ['train a very small decoder','two-layer numpy','fit a classifier','adaptation run']:
            self.assertNotIn(obsolete,builds)

if __name__=='__main__':unittest.main()
