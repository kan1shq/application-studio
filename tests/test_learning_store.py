import json
import sqlite3
import unittest
from unittest.mock import patch
from contextlib import contextmanager
from types import SimpleNamespace
import learning_store as store

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:'); self.db.row_factory=sqlite3.Row
        store.initialize(self.db)
        self.catalog={'items':[{'id':'problem:one','kind':'dsa'},{'id':'design:one','kind':'systems'}]}
    def tearDown(self): self.db.close()
    def test_progress_and_conflict(self):
        body={'id':'problem:one','status':'studied','notes':'Keep notes','evidence':'C:/evidence.txt','version':0}
        self.assertEqual(store.save_state(self.db,self.catalog,body)['state']['version'],1)
        self.db.commit()
        with self.assertRaises(store.Conflict): store.save_state(self.db,self.catalog,body)
        self.db.rollback()
        self.assertEqual(store.view(self.db)['states']['problem:one']['notes'],'Keep notes')
    def test_attempt_retries_and_no_mastery(self):
        store.attempt(self.db,self.catalog,{'id':'problem:one','day':135,'outcome':'independent','minutes':20,'hints':0})
        state=store.view(self.db)
        self.assertEqual([r['due_day'] for r in state['retries']],[137,142,149])
        self.assertEqual([r['backlog'] for r in state['retries']],[False,True,True])
        self.assertEqual(state['states'],{})
    def test_migration_preserves_prep_and_first_definition(self):
        self.db.execute('CREATE TABLE prep_state(day INTEGER PRIMARY KEY,payload TEXT)')
        payload=json.dumps({'tasks':[1],'notes':'Original','energy':'standard'})
        self.db.execute('INSERT INTO prep_state VALUES (1,?)',(payload,))
        self.db.execute('INSERT INTO prep_state VALUES (2,?)',(json.dumps({'tasks':[],'notes':''}),))
        @contextmanager
        def connect(): yield self.db
        app=SimpleNamespace(connect=connect)
        store.migrate_sessions(app,{'days':[{'day':1,'title':'Old'},{'day':2,'title':'Empty'}]})
        store.migrate_sessions(app,{'days':[{'day':1,'title':'New'}]})
        self.assertEqual(store.view(self.db)['sessions']['1']['definition']['title'],'Old')
        self.assertNotIn('2',store.view(self.db)['sessions'])
        self.assertEqual(self.db.execute('SELECT payload FROM prep_state WHERE day=1').fetchone()[0],payload)
    def imported(self,items,complete=True):
        return store.import_snapshot(self.db,{'source_url':'https://www.fanout.sh/blog','observed_at':'2026-10-05T00:00:00Z','items':items,'complete':complete})
    def test_import_adoption_and_failure_retention(self):
        first=self.imported([{'url':'https://fanout.ai/blog/one','title':'One','access':'public'}])
        store.adopt(self.db,{'snapshot_id':first['id'],'item_id':first['items'][0]['id']})
        store.known(self.db,self.catalog,first['items'][0]['id'])
        partial=self.imported([],False)
        self.assertEqual(partial['diff']['removals'],[])
        with patch.object(store,'open_public',side_effect=RuntimeError('HTTP 403')):
            result=store.refresh(self.db,{'source_url':'https://www.fanout.sh/blog'})
        self.assertTrue(result['retained']); self.assertEqual(len(store.view(self.db)['snapshots']),2)
        with self.assertRaises(ValueError): self.imported([{'url':'http://localhost/private','title':'Bad','access':'public'}])
    def test_complete_removal(self):
        self.imported([{'url':'https://fanout.ai/blog/one','title':'One','access':'public'}])
        self.assertEqual(len(self.imported([])['diff']['removals']),1)
    def test_readopt_updates_same_id_and_duplicate_is_idempotent(self):
        original={'url':'https://fanout.ai/blog/one','title':'Original lesson','access':'public','summary':'Old outline'}
        first=self.imported([original])
        item_id=first['items'][0]['id']
        store.adopt(self.db,{'snapshot_id':first['id'],'item_id':item_id})
        self.db.commit()
        store.save_state(self.db,{'items':[{'id':item_id,'kind':'reference'}]}, {'id':item_id,'status':'studied','notes':'Keep my notes','evidence':'artifact.txt','version':0})
        second=self.imported([dict(original,title='Updated lesson',access='mixed',summary='New outline')])
        self.assertEqual(second['items'][0]['id'],item_id)
        body={'snapshot_id':second['id'],'item_id':item_id}
        updated=store.adopt(self.db,body)['item']
        self.assertEqual(updated['title'],'Updated lesson')
        self.assertEqual(store.adopt(self.db,body)['item'],updated)
        state=store.view(self.db)
        self.assertEqual(len(state['adoptions']),1)
        self.assertEqual(state['adoptions'][0]['summary'],'New outline')
        self.assertEqual(state['adoptions'][0]['snapshot_id'],second['id'])
        self.assertEqual(state['states'][item_id]['notes'],'Keep my notes')
    def test_latest_dsa_retry_schedule_only(self):
        body={'id':'problem:one','day':3,'outcome':'unsolved','minutes':20,'hints':0}
        store.attempt(self.db,self.catalog,body); self.db.commit()
        store.attempt(self.db,self.catalog,dict(body,day=5,outcome='independent')); self.db.commit()
        store.attempt(self.db,self.catalog,dict(body,id='design:one',score=20)); self.db.commit()
        state=store.view(self.db,self.catalog)
        self.assertEqual([r['due_day'] for r in state['retries']],[7,12,19])
        self.assertEqual(len(state['attempts']),3)
        self.assertEqual(state['states'],{})
    def test_rubric_hints_and_nonce(self):
        body={'id':'design:one','day':3,'outcome':'independent','minutes':20,'hints':0,'score':20,'client_nonce':'one'}
        first=store.attempt(self.db,self.catalog,body); self.db.commit()
        second=store.attempt(self.db,self.catalog,body); self.db.commit()
        self.assertEqual(first['attempt_id'],second['attempt_id'])
        self.assertEqual(len(store.view(self.db)['attempts']),1)
        with self.assertRaises(ValueError): store.attempt(self.db,self.catalog,dict(body,score=21))
        with self.assertRaises(ValueError): store.attempt(self.db,self.catalog,dict(body,hints=1))
    def test_repeated_url_source_keys(self):
        item={'url':'https://www.fanout.sh/updates','title':'Update','access':'mixed'}
        snapshot=self.imported([dict(item,source_key='2026-10-01'),dict(item,source_key='2026-10-02'),item])
        self.assertEqual(len({i['id'] for i in snapshot['items']}),3)
        self.assertEqual(snapshot['items'][0]['source_key'],'2026-10-01')
        with self.assertRaises(ValueError): self.imported([dict(item,source_key='one'),dict(item,source_key='one')])

if __name__=='__main__': unittest.main()
