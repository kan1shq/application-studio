"""Read-only checks for deterministic curriculum generation."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from tools.consolidate_curriculum import consolidate, source_id
from tools.build_curriculum import compile_catalog, outputs

ROOT=Path(__file__).resolve().parents[1]

class CurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=json.loads((ROOT/'data/plan.json').read_text(encoding='utf-8-sig'))
        # Once integration generates plan.json, preserve the original embedded seed.
        catalog_path=ROOT/'data/curriculum.json'
        if catalog_path.exists(): cls.base=json.loads(catalog_path.read_text(encoding='utf-8-sig'))['base_plan']
        cls.inventory=[{'source_url':'https://www.fanout.sh/system/overview','observed_at':'2026-10-05T00:00:00Z','complete':True,'items':[{'url':'https://www.fanout.sh/system/archive/api-design','title':'HTTP API contracts','module':'Foundations','kind':'lesson','access':'free'}],'free_details':[{'url':'https://www.fanout.sh/system/archive/api-design','headings':['Public API outline'],'links':[{'url':'https://www.rfc-editor.org/rfc/rfc9110.html','title':'HTTP semantics'}]}]}]
        cls.catalog=consolidate(cls.base,cls.inventory)
    def test_inventory_and_budget_preserved(self):
        plan=compile_catalog(self.catalog)
        self.assertEqual(len(plan['days']),140); self.assertEqual(len(plan['projects']),15)
        self.assertEqual(sum(len(w.get('questions',[])) for w in plan['weeks']),80)
        self.assertEqual([t['minutes'] for t in plan['days'][0]['core_tasks']],[60,45,60,15])
        self.assertEqual(plan['days'][0]['project_id'],'weekend_1')
        self.assertTrue(plan['days'][0].get('ai_theory'))
        for week in range(1,21): self.assertEqual(sum(sum(t['minutes'] for t in d['core_tasks']) for d in plan['days'] if d['week']==week),1260)
    def test_deterministic_and_pure(self):
        original=copy.deepcopy(self.catalog)
        first=outputs(self.catalog); second=outputs(self.catalog)
        self.assertEqual(first,second); self.assertEqual(original,self.catalog)
        self.assertEqual(self.base,self.catalog['base_plan'])
        self.assertIn('Searchable catalog',first['reports/fanout-plan/learning-library-plan.html'])
        self.assertEqual(first['dist/learning-library-plan.html'],first['reports/fanout-plan/learning-library-plan.html'])
        self.assertIn('Day 140',first['reports/140_DAY_PLAN.md'])
        self.assertNotIn('## Day 71',first['reports/70_DAY_PLAN.md'])
    def test_task_crosswalk_and_exercise_timeboxes(self):
        plan=compile_catalog(self.catalog); ids={i['id'] for i in self.catalog['items']}
        self.assertEqual(sum(i['kind']=='exercise' for i in self.catalog['items']),39)
        for d in plan['days']:
            for task in d['core_tasks']:
                self.assertTrue(task['item_ids']); self.assertTrue(set(task['item_ids'])<=ids)
                self.assertLessEqual(task.get('exercise_minutes',0),task['minutes'])
        for item in self.catalog['items']:
            self.assertTrue(item['source_urls']); self.assertTrue(item['resource_ids'])
            self.assertIn(item['placement'],{'core','reference','unavailable'})
    def test_stable_source_id_and_public_outline(self):
        raw=self.inventory[0]['items'][0]
        expected='fanout:'+hashlib.sha256(raw['url'].encode()).hexdigest()[:20]
        self.assertEqual(source_id(raw),expected)
        source=next(i for i in self.catalog['items'] if i['id']==expected)
        self.assertEqual(source['placement'],'reference'); self.assertEqual(source['assignments'],[])
        self.assertEqual(source['source_outline']['headings'],['Public API outline'])
        self.assertTrue(any(r.startswith('ref:') for r in source['resource_ids']))
        keyed=source_id(dict(raw,source_key='dated'))
        self.assertNotEqual(keyed,expected)
    def test_authoritative_exercise_assignment_and_overload(self):
        review={'exercise_assignments':[{'id':'E01','day':2,'block':'systems','minutes':30}]}
        catalog=consolidate(self.base,[],review)
        exercise=next(i for i in catalog['items'] if i['id']=='exercise:E01')
        self.assertEqual(exercise['assignments'],[{'day':2,'block':1,'minutes':30}])
        broken=copy.deepcopy(catalog)
        next(i for i in broken['items'] if i['id']=='exercise:E01')['assignments'][0]['minutes']=500
        with self.assertRaises(ValueError): compile_catalog(broken)
    def test_prerequisites_and_shared_readiness(self):
        by_id={i['id']:i for i in self.catalog['items']}
        for item in self.catalog['items']:
            for prerequisite in item.get('prerequisites',[]):
                self.assertIn(prerequisite,by_id)
                if item['assignments'] and by_id[prerequisite]['assignments']:
                    self.assertLessEqual(min(a['day'] for a in by_id[prerequisite]['assignments']),min(a['day'] for a in item['assignments']))
        cp=by_id['checkpoint:70']
        self.assertIn('Three independent coding mocks',cp['criteria'][0])
        self.assertEqual(sum(i.startswith('dsa:mock') for i in cp['evidence_ids']),3)
        self.assertEqual(sum(i.startswith('systems:') for i in cp['evidence_ids']),3)
    def test_richer_metadata_wins_duplicate_capture(self):
        capture=copy.deepcopy(self.inventory[0]); capture['source_url']='https://www.fanout.sh/resources'
        capture['items'][0].update(title='Generic reference',kind='topic'); capture.pop('free_details')
        catalog=consolidate(self.base,[capture,self.inventory[0]])
        source=next(i for i in catalog['items'] if i['id']==source_id(capture['items'][0]))
        self.assertEqual(source['kind'],'lesson'); self.assertEqual(source['title'],'HTTP API contracts')
        self.assertIn('https://www.fanout.sh/resources',source['source_urls'])
    def test_review_resource_mapping_and_alias_contract(self):
        review=json.loads((ROOT/'data/curriculum.json').read_text(encoding='utf-8-sig'))['review']
        catalog=consolidate(self.base,self.inventory,review)
        source=next(i for i in catalog['items'] if i['id']==source_id(self.inventory[0]['items'][0]))
        self.assertEqual(source['primary_resource_id'],'S03')
        self.assertEqual(source['deep_resource_ids'][0],'S01')
        self.assertIn('S15',{r['id'] for r in catalog['resources']})
        for i in catalog['items']:
            self.assertEqual(i['prerequisite_ids'],i['prerequisites'])
            self.assertEqual(i['assigned_days'],sorted({a['day'] for a in i['assignments']}))
        plan=compile_catalog(catalog)
        self.assertEqual(len(plan['learning_library']['exercises']),39)
        cp=next(i for i in catalog['items'] if i['id']=='checkpoint:70')
        self.assertIn('milestone:weekend_4:explain',cp['evidence_ids'])
        self.assertIn('systems:day-40',cp['evidence_ids'])
    def test_external_paper_primary_is_actual_reference(self):
        capture={'source_url':'https://www.fanout.sh/papers','observed_at':'2026-10-05','complete':True,'items':[{'kind':'paper','title':'Some primary research','access':'free','url':'https://arxiv.org/abs/1234.5678'}]}
        catalog=consolidate(self.base,[capture]); item=next(i for i in catalog['items'] if i['id']==source_id(capture['items'][0]))
        resource=next(r for r in catalog['resources'] if r['id']==item['primary_resource_id'])
        self.assertEqual(resource['url'],capture['items'][0]['url'])

if __name__=='__main__': unittest.main()
