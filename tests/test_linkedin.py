import importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import linkedin_search as li

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('linkedin_test_server',ROOT/'server.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
CARD='''<ul><li><div class="base-search-card" data-entity-urn="urn:li:jobPosting:123"><img alt=""><h3 class="base-search-card__title">Python &amp; AI Engineer</h3><h4 class="base-search-card__subtitle"><a>Example Co</a></h4><span class="job-search-card__location">Bengaluru, India</span><time datetime="2026-10-05">Today</time></div></li></ul>'''
DETAIL='<section class><div class="show-more-less-html__markup"><p>Python services, RAG evaluation and SQL.</p></div></section>'

class ParserMatchingTests(unittest.TestCase):
    def test_card_and_description_fields(self):
        j=li.parse_cards(CARD)[0]
        self.assertEqual(j['id'],'123');self.assertEqual(j['company'],'Example Co')
        self.assertEqual(j['title'],'Python & AI Engineer')
        self.assertIn('RAG',li.parse_description(DETAIL))
        self.assertEqual(li.job_id('https://in.linkedin.com/jobs/view/title-at-company-123?trk=x'),'123')
        self.assertIsNone(li.job_id('https://linkedin.com.evil.test/jobs/view/123'))
    def test_word_boundaries_unknown_and_title_exclusions(self):
        cfg=li.validate(dict(li.DEFAULTS,keywords='Java, Go',exclude='staff',mode='any'))
        j={'title':'JavaScript Engineer','company':'Goose','location':'India','scan_text':''}
        self.assertEqual(li.match(j,cfg)['match_status'],'unknown')
        j['scan_text']='JavaScript programming is ongoing.'
        self.assertEqual(li.match(j,cfg)['match_status'],'no_match')
        j['scan_text']='Go and Java development.'
        self.assertEqual(li.match(j,cfg)['matched'],['Java','Go'])
        j['title']='Staff Engineer'
        self.assertEqual(li.match(j,cfg)['match_status'],'excluded')
    def test_input_and_url_boundaries(self):
        for invalid in [dict(li.DEFAULTS,limit=True),dict(li.DEFAULTS,pages=True),dict(li.DEFAULTS,pages=11),dict(li.DEFAULTS,pages=0),dict(li.DEFAULTS,query=''),dict(li.DEFAULTS,posted='forever')]:
            with self.assertRaises(ValueError):li.validate(invalid)
        for url in ['http://www.linkedin.com/jobs/search/','https://www.linkedin.com/login','https://localhost/jobs/search/','https://www.linkedin.com@evil.test/jobs/search/']:
            self.assertFalse(li.allowed_url(url))
        with self.assertRaises(li.Blocked):
            li.SafeRedirect().redirect_request(None,None,302,'',{},'https://www.linkedin.com/authwall')

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();app.DATA=Path(self.temp.name);app.DB_PATH=app.DATA/'test.sqlite';app.initialize()
        self.ctx=app.linkedin_context();self.cfg=li.validate(dict(li.DEFAULTS,keywords='RAG',exclude='',pages=1))
        self.job=li.match(dict(li.parse_cards(CARD)[0],scan_text='Python and RAG'),self.cfg)
        self.data={'jobs':[self.job],'config':self.cfg,'results_config':self.cfg,'status':'complete','checked_at':'2026-10-05T00:00:00Z'}
        li.store(self.ctx,self.data)
    def tearDown(self):
        li.STATUS.update(running=False);self.temp.cleanup()
    def test_track_idempotent_preserves_notes_and_distinct_source(self):
        first=li.track(self.ctx,'123')
        with app.connect() as db:db.execute('INSERT INTO job_state VALUES (?,?,?,?)',(first['id'],'Applied','Keep this note','today'))
        self.assertTrue(li.track(self.ctx,'123')['existing'])
        with app.connect() as db:
            self.assertEqual(db.execute('select count(*) from jobs').fetchone()[0],1)
            self.assertEqual(db.execute('select notes from job_state').fetchone()[0],'Keep this note')
        j=app.snapshot()['jobs'][0]
        self.assertEqual(j['status_source'],'linkedin_snapshot');self.assertIsNone(j['verified_at'])
    def test_rematch_reuses_data_without_network_and_keeps_timestamp(self):
        with patch.object(li,'fetch_page',side_effect=AssertionError('No network allowed')):
            li.rematch(self.ctx,dict(self.cfg,keywords='Rust'))
        current=li.view(self.ctx)
        self.assertEqual(current['jobs'][0]['match_status'],'no_match')
        self.assertEqual(current['checked_at'],self.data['checked_at'])
        self.assertNotIn('scan_text',current['jobs'][0])
        with self.assertRaises(ValueError):li.rematch(self.ctx,dict(self.cfg,location='Germany'))
    def test_blocked_search_retains_previous_results(self):
        pending=dict(self.data,status='running');run_id=li.store(self.ctx,pending)
        li.LOCK.acquire();li.STATUS.update(running=True)
        with patch.object(li,'fetch_page',side_effect=li.Blocked('HTTP 429')):
            li.run(self.ctx,self.cfg,run_id,pending)
        result=li.latest(self.ctx)
        self.assertEqual(result['status'],'error');self.assertEqual(result['jobs'][0]['id'],'123')
        self.assertFalse(li.STATUS['running']);self.assertFalse(li.LOCK.locked())
    def test_search_refresh_deduplicates_and_matches_details(self):
        pending=dict(self.data,status='running');run_id=li.store(self.ctx,pending)
        li.LOCK.acquire();li.STATUS.update(running=True)
        with patch.object(li,'fetch_page',side_effect=[CARD+CARD,DETAIL]),patch.object(li.time,'sleep'):
            li.run(self.ctx,self.cfg,run_id,pending)
        result=li.latest(self.ctx)
        self.assertEqual(len(result['jobs']),1)
        self.assertEqual(result['jobs'][0]['match_status'],'match')
        self.assertEqual(result['description_count'],1)

    def test_later_failure_keeps_new_pages_and_stops_all_requests(self):
        cfg=dict(self.cfg,pages=5)
        pending=dict(self.data,status='running');run_id=li.store(self.ctx,pending)
        li.LOCK.acquire();li.STATUS.update(running=True)
        with patch.object(li,'fetch_page',side_effect=[CARD.replace('123','456'),li.Blocked('HTTP 429')]) as fetch,patch.object(li.time,'sleep'):
            li.run(self.ctx,cfg,run_id,pending)
        result=li.latest(self.ctx)
        self.assertEqual(result['status'],'partial')
        self.assertEqual([j['id'] for j in result['jobs']],['456'])
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(result['pagination']['stop_reason'],'request_failed')
        li.rematch(self.ctx,dict(cfg,keywords='Python'))
        self.assertEqual(li.latest(self.ctx)['status'],'partial')

class PaginationTests(unittest.TestCase):
    def collect(self,responses,**config):
        with patch.object(li,'fetch_page',side_effect=responses) as fetch,patch.object(li.time,'sleep'):
            result=li.collect_pages(dict(li.DEFAULTS,**config))
        return result,fetch.call_args_list

    def test_offsets_follow_batch_sizes_and_deduplicate_overlap(self):
        (jobs,warnings,meta,failed),calls=self.collect([CARD+CARD.replace('123','124'),CARD.replace('123','124')+CARD.replace('123','125'),''])
        self.assertEqual([j['id'] for j in jobs],['123','124','125'])
        self.assertIn('start=2',calls[1].args[0]);self.assertIn('start=4',calls[2].args[0])
        self.assertIn('/jobs-guest/jobs/api/seeMoreJobPostings/search?',calls[1].args[0])
        self.assertEqual(meta['stop_reason'],'end_of_results');self.assertFalse(failed)

    def test_duplicate_page_and_page_limit_stop(self):
        (_,_,meta,_),calls=self.collect([CARD,CARD])
        self.assertEqual(len(calls),2);self.assertEqual(meta['stop_reason'],'no_new_jobs')
        (_,_,meta,_),calls=self.collect([CARD],pages=1)
        self.assertEqual(len(calls),1);self.assertEqual(meta['stop_reason'],'page_limit')

    def test_result_cap_stops_without_extra_request(self):
        page=''.join(CARD.replace('123',str(i)) for i in range(12))
        (jobs,_,meta,_),calls=self.collect([page],limit=10)
        self.assertEqual(len(jobs),10);self.assertEqual(len(calls),1)
        self.assertEqual(meta['stop_reason'],'result_limit')

    def test_unrecognized_markup_retains_partial_without_claiming_end(self):
        (jobs,warnings,meta,failed),calls=self.collect([CARD,'<html>Sign in</html>'])
        self.assertEqual(len(jobs),1);self.assertTrue(failed);self.assertTrue(warnings)
        self.assertEqual(meta['stop_reason'],'request_failed')

if __name__=='__main__':unittest.main()
