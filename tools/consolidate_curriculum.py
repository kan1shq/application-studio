"""Bootstrap a canonical catalog from the current plan and captured public metadata.

No imports of the older builders, database reads or import-time writes occur.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse
try:
    from .build_curriculum import ROOT, VERSION, BLOCKS, normalize_plan, compile_catalog
except ImportError:
    from build_curriculum import ROOT, VERSION, BLOCKS, normalize_plan, compile_catalog

def slug(value):
    return re.sub(r'[^a-z0-9]+','-',str(value).lower()).strip('-')

def source_id(raw):
    identity=raw['url']+('#'+raw['source_key'] if 'source_key' in raw else '')
    return 'fanout:'+hashlib.sha256(identity.encode()).hexdigest()[:20]

def resource_pair(track,title=''):
    lower=title.lower()
    if track=='systems':
        if any(word in lower for word in ('index','query','postgres','sql')): return ['S04','S08']
        if any(word in lower for word in ('http','dns','tls','api')): return ['S07','S01']
        if any(word in lower for word in ('slo','observ','incident','overload','monitor')): return ['S03','S01']
        return ['S01','S03']
    if track=='math': return ['A01','A06']
    if track=='inference': return ['A04','A14']
    if track=='dsa': return ['D01']
    if track=='career': return ['S14']
    return ['A02','A09']

def source_track(source):
    path=urlparse(source).path
    if path.startswith('/system') or path=='/roadmaps/system-design': return 'systems'
    if path.startswith('/ml-math') or path in {'/math-decoder','/roadmaps/ml-math'}: return 'math'
    if path.startswith('/inference-eng') or path=='/roadmaps/inference-engineering': return 'inference'
    return 'ai'

def make_item(item_id,kind,title,track,resources,**fields):
    pair=[r for r in resource_pair(track,title) if r in resources]
    if not pair: pair=[next(iter(resources))]
    item={'id':item_id,'kind':kind,'title':title,'track':track,'placement':'core','assignments':[], 'prerequisites':[], 'related_ids':[], 'resource_ids':pair,'primary_resource_id':pair[0],'deep_resource_ids':pair[1:],'source_urls':[resources[r]['url'] for r in pair]}
    item.update(fields)
    return item

def apply_resource_group(item,group,resources):
    primary=[r for r in group.get('primary_resource_ids',[]) if r in resources][:1]
    deep=[r for r in group.get('deep_resource_ids',[]) if r in resources][:1]
    if not primary: return
    extra=[r for r in item.get('resource_ids',[]) if r.startswith('ref:')]
    related=[r for r in group.get('related_resource_ids',[]) if r in resources]
    item.update(primary_resource_id=primary[0],deep_resource_ids=list(dict.fromkeys(deep+extra)),resource_ids=list(dict.fromkeys(primary+deep+extra+related)),related_resource_ids=related)

def review_groups(review):
    result=[]
    for domain in review.get('topic_groups',[]):
        track={'ml_math':'math'}.get(domain['domain'],domain['domain'])
        for group in domain.get('groups',[]): result.append(dict(group,track=track))
    return result

def normalize_assignments(review):
    source=review.get('exercise_assignments',[])
    if isinstance(source,dict):
        source=[dict(a,id=key) for key,values in source.items() for a in (values if isinstance(values,list) else [values])]
    mapped=defaultdict(list)
    for assignment in source:
        if not isinstance(assignment,dict): raise ValueError('Invalid exercise assignment')
        key=assignment.get('exercise_id',assignment.get('id',assignment.get('item_id')))
        if not key: raise ValueError('Exercise assignment requires an ID')
        key=key.removeprefix('exercise:')
        block=assignment.get('block',assignment.get('block_index'))
        if isinstance(block,str):
            if block.lower() not in BLOCKS: raise ValueError('Unknown exercise block '+block)
            block=BLOCKS[block.lower()]
        if type(block) is not int: raise ValueError('Invalid exercise block')
        mapped[key].append({'day':assignment['day'],'block':block,'minutes':assignment['minutes'],**({'replace_note':assignment['replace_note']} if assignment.get('replace_note') else {})})
    return mapped

def consolidate(base_plan,inventory=None,review=None):
    plan=normalize_plan(base_plan)
    inventory=inventory or []; review=review or {}
    if isinstance(inventory,dict): inventory=inventory.get('captures',inventory.get('sources',[]))
    resources=copy.deepcopy(plan['learning_library']['resources'])
    for suggestion in review.get('gap_resource_suggestions',[]):
        if not any(r['id']==suggestion['resource'] for r in resources):
            resources.append({'id':suggestion['resource'],'title':suggestion['title'],'url':suggestion['url'],'category':'Systems' if suggestion['resource'].startswith('S') else 'AI','kind':'Reviewed primary reference','access':'Public primary source','description':suggestion['why'],'use':'Primary reading' if suggestion.get('core_or_reference')=='core' else 'Optional deep reference','review_topic':suggestion['topic']})
    if not any(r['id']=='D01' for r in resources):
        link=next((r for d in plan['days'] for r in d.get('resources',[]) if 'neetcode' in r['url']),{'label':'NeetCode roadmap','url':'https://neetcode.io/practice/practice/neetcode150'})
        resources.append({'id':'D01','title':link['label'],'url':link['url'],'category':'DSA','kind':'Roadmap','access':'Free','description':'Existing coding practice reference; evidence comes from independent attempts.','use':'Primary reading'})
    res={r['id']:r for r in resources}
    items={}
    def add(item):
        if item['id'] in items: raise ValueError('Duplicate canonical ID '+item['id'])
        items[item['id']]=item
        return item
    days={d['day']:d for d in plan['days']}; weeks={w['week']:w for w in plan['weeks']}
    for w in plan['weeks']:
        for q in w.get('questions',[]):
            key=f"dsa:lc-{q['id']}"
            if key not in items:
                add(make_item(key,'dsa',f"LC {q['id']}: {q['title']}",'dsa',res,url=q['url'],source_urls=[q['url']],difficulty=q['difficulty'],leetcode_id=q['id'],item_type='problem',week=w['week'],summary='Independent coding target: explain invariant, complexity, tests and hints used. Unsolved remains unsolved.'))
        add(make_item(f"dsa:mock-w{w['week']}",'dsa',f"Week {w['week']} timed coding mock",'dsa',res,item_type='mock',week=w['week'],summary='Independent unseen coding attempt within the existing DSA timebox; record outcome, hints, complexity and edge cases.'))
    for d in plan['days']:
        weekday=(d['day']-1)%7
        if weekday>=5: continue
        if weekday==4:
            items[f"dsa:mock-w{d['week']}"]['assignments'].append({'day':d['day'],'block':0})
        else:
            questions=re.findall(r'\bLC\s+(\d+)\b',d['core_tasks'][0]['task'])
            if not questions: questions=[str(q['id']) for q in weeks[d['week']].get('questions',[])[weekday*2:weekday*2+2]]
            if questions:
                for q in dict.fromkeys(questions):
                    if f'dsa:lc-{q}' not in items: raise ValueError('Task references unknown LC '+q)
                    items[f'dsa:lc-{q}']['assignments'].append({'day':d['day'],'block':0})
            else:
                add(make_item(f"dsa:review-day-{d['day']}",'dsa',f"Day {d['day']} coding maintenance",'dsa',res,item_type='maintenance',assignments=[{'day':d['day'],'block':0}],summary='Select a due retry or unseen variant from the existing question inventory inside this block. This does not add a new required question.'))
        for block,track in ((1,'systems'),(2,'ai'),(3,'career')):
            task=d['core_tasks'][block]
            if track=='systems': title=weeks[d['week']]['system_topics'][weekday]
            elif track=='ai': title=d.get('ai_theory',{}).get('title') or task['task'].split(':',1)[-1].strip().split('.')[0]
            else: title=task['task'].split('.')[0]
            add(make_item(f"{track}:day-{d['day']}",track,title,track,res,assignments=[{'day':d['day'],'block':block}],day=d['day'],week=d['week'],task=task['task'],summary='Independent study focus: '+task['task'],done_when=task.get('done_when','')))
    for p in plan['projects']:
        scheduled=[d for d in plan['days'] if d['project_id']==p['id']]
        weekends=[d for d in scheduled if (d['day']-1)%7>=5]
        first=min(d['day'] for d in scheduled)
        theory=[f'systems:day-{first}',f'ai:day-{first}']
        project=add(make_item('project:'+p['id'],'project',p['name'],'ai',res,project_id=p['id'],week=p['week'],prerequisites=theory,source_urls=[p['resource']],summary=p['problem'],task=p['build'],done_when=p['proof'],assignments=[{'day':d['day'],'block':0} for d in weekends],acceptance=p['test'],stop=p['stop']))
        for stage,key in (('build','build'),('evaluate','test'),('explain','proof')):
            assignments=[]
            for d in weekends:
                if (d['day']-1)%7==5:
                    if stage=='build': assignments.extend([{'day':d['day'],'block':0},{'day':d['day'],'block':1}])
                    if stage=='evaluate': assignments.append({'day':d['day'],'block':2})
                else:
                    if stage=='evaluate': assignments.extend([{'day':d['day'],'block':0},{'day':d['day'],'block':1}])
                    if stage=='explain': assignments.append({'day':d['day'],'block':2})
            milestone=add(make_item(f"milestone:{p['id']}:{stage}",'milestone',p['name']+' — '+stage,'ai',res,project_id=p['id'],stage=stage,prerequisites=theory if stage=='build' else [f"milestone:{p['id']}:{'build' if stage=='evaluate' else 'evaluate'}"],related_ids=[project['id']],source_urls=[p['resource']],summary=p[key],assignments=assignments))
            project['related_ids'].append(milestone['id'])
    assignment_map=normalize_assignments(review)
    used=defaultdict(int)
    for exercise in plan['learning_library']['exercises']:
        key=exercise['id']; track='systems' if exercise['category'].lower()=='systems' else 'math' if exercise['category'].lower()=='math' else 'ai'
        assignments=assignment_map.get(key)
        if assignments is None:
            week=int(re.search(r'\d+',str(exercise['week'])).group()) if re.search(r'\d+',str(exercise['week'])) else 20
            block=1 if track=='systems' else 2; remaining=exercise['minutes']; assignments=[]
            for d in plan['days']:
                if d['week']!=week or (d['day']-1)%7>=5: continue
                available=d['core_tasks'][block]['minutes']-used[(d['day'],block)]
                minutes=min(available,remaining)
                if minutes>0:
                    assignments.append({'day':d['day'],'block':block,'minutes':minutes}); remaining-=minutes
                if remaining==0: break
            if remaining: raise ValueError('No capacity for exercise '+key)
        for a in assignments: used[(a['day'],a['block'])]+=a['minutes']
        add(make_item('exercise:'+key,'exercise',exercise['title'],track,res,exercise_id=key,week=exercise['week'],minutes=exercise['minutes'],task=exercise['task'],summary='Independent practical exercise: '+exercise['task'],done_when=exercise['evidence'],evidence=exercise['evidence'],assignments=copy.deepcopy(assignments)))
    unknown=set(assignment_map)-{e['id'] for e in plan['learning_library']['exercises']}
    if unknown: raise ValueError('Unknown assigned exercises: '+','.join(sorted(unknown)))
    for cp in plan['learning_library']['checkpoints']:
        checkpoint=copy.deepcopy(cp)
        if cp['day']==70:
            checkpoint['criteria']=['Three independent coding mocks with invariants, complexity and edge cases.','Three system-design mocks scored with the shared 0–20 rubric.','Six experience stories with personal, team and AI-assisted contributions separated.','Two runnable, explainable projects with evaluation boundaries and honest limitations.']
        readiness=review.get('readiness',{})
        schedule={s['type']:s.get('days',[]) for s in readiness.get('schedule',[])}
        friday_days=[d for d in days if d<=cp['day'] and (d-1)%7==4][-3:]
        coding_days=[d for d in schedule.get('coding_mock',friday_days) if d<=cp['day']][-3:]
        design_days=[d for d in schedule.get('design_mock',friday_days) if d<=cp['day']][-3:]
        evidence=[f"dsa:mock-w{days[d]['week']}" for d in coding_days]+[f'systems:day-{d}' for d in design_days]
        completed=[p for p in plan['projects'] if any(d['project_id']==p['id'] and d['day']<=cp['day'] and (d['day']-1)%7==6 for d in plan['days'])][-2:]
        if readiness.get('project_proofs'):
            selected={p['project_id'] for p in readiness['project_proofs'] if p['due_by_day']<=cp['day']}
            completed=[p for p in plan['projects'] if p['id'] in selected]
        evidence += [f"milestone:{p['id']}:{stage}" for p in completed for stage in ('build','evaluate','explain')]
        story_days=schedule.get('behavioral_story',[d for d in sorted(days) if d<=cp['day'] and (d-1)%7<5][-6:])
        evidence += [f"career:day-{d}" for d in story_days if d<=cp['day']][-6:]
        add(make_item(f"checkpoint:{cp['day']}",'checkpoint',cp['title'],'career',res,day=cp['day'],criteria=checkpoint['criteria'],evidence_ids=evidence,related_ids=evidence,summary='Review existing evidence within this day; do not add extra mocks or builds.',assignments=[{'day':cp['day'],'block':len(days[cp['day']]['core_tasks'])-1}]))
    source_inventory=[]; groups=defaultdict(list)
    for capture in inventory:
        source=capture['source_url']; track=source_track(source)
        source_inventory.append({k:copy.deepcopy(v) for k,v in capture.items() if k not in {'items','free_details','details'}}|{'item_count':len(capture.get('items',[])),'free_outline_count':len(capture.get('free_details',[])),'public_group_detail_count':len(capture.get('details',[]))})
        for raw in capture.get('items',[]):
            sid=source_id(raw)
            if sid in items:
                if source not in items[sid]['source_urls']: items[sid]['source_urls'].append(source)
                priority={'navigation':0,'topic':1,'update':2,'paper':3,'lesson':4}
                if priority.get(raw.get('kind'),1)>priority.get(items[sid]['kind'],1):
                    items[sid].update(kind=raw['kind'],title=raw['title'],track=track)
                    for field in ('access','module','code'):
                        if field in raw: items[sid][field]=raw[field]
            else:
                kind=raw.get('kind','paper' if urlparse(source).path=='/papers' else 'lesson')
                if kind not in {'lesson','topic','paper','update','navigation'}: kind='topic'
                fields={k:raw[k] for k in ('url','access','module','code','source_key') if k in raw}
                fields['source_kind']=raw.get('kind','lesson')
                if raw.get('summary'): fields['source_note']=raw['summary']
                item=make_item(sid,kind,raw['title'],track,res,placement='unavailable' if raw.get('access')=='announced' else 'reference',source_urls=list(dict.fromkeys([source,raw['url']])),summary='Independent study focus: '+raw['title']+'. Use the primary reference to explain mechanisms, assumptions and one failure case. This objective is ours; the public title is metadata, not a paid lesson paraphrase.',**fields)
                add(item)
            source_item=items[sid]
            if urlparse(raw['url']).hostname not in {'fanout.sh','www.fanout.sh'}:
                rid=next((r['id'] for r in resources if r['url']==raw['url']),None)
                if rid is None:
                    rid='ref:'+hashlib.sha256(raw['url'].encode()).hexdigest()[:20]
                    resource={'id':rid,'url':raw['url'],'title':raw['title'],'category':track,'kind':'Paper' if source_item['kind']=='paper' else 'Public reference link','access':raw.get('access','Linked; access not independently checked'),'description':'Primary target linked by the captured public inventory.','use':'Primary reference for this item'}
                    resources.append(resource); res[rid]=resource
                source_item.update(primary_resource_id=rid,resource_ids=[rid],deep_resource_ids=[])
            module=raw.get('module') or 'Public '+urlparse(source).path.strip('/')
            groups[(source,module,track)].append(sid)
        for detail in capture.get('free_details',[])+capture.get('details',[]):
            matching=[i for i in items.values() if i.get('url')==detail['url'] and i['id'].startswith('fanout:')]
            for item in matching:
                item['public_outline']=list(dict.fromkeys(detail.get('headings',[])))
                item['public_steps']=copy.deepcopy(detail.get('steps',[]))
                item['source_outline']={'headings':item['public_outline'],'steps':item['public_steps']}
                item['outline_provenance']='Headings and step labels captured from a publicly readable page; no lesson body copied.'
                for link in detail.get('links',[]):
                    parsed=urlparse(link.get('url',''))
                    if parsed.scheme not in {'https','http'} or not parsed.hostname or parsed.hostname in {'fanout.sh','www.fanout.sh'}: continue
                    rid='ref:'+hashlib.sha256(link['url'].encode()).hexdigest()[:20]
                    if rid not in res:
                        resource={'id':rid,'url':link['url'],'title':link.get('title') or parsed.hostname,'category':item['track'],'kind':'Public reference link','access':'Linked; access not independently checked','description':'External reference linked from a publicly readable source outline.','use':'Optional deep reference'}
                        resources.append(resource); res[rid]=resource
                    if rid not in item['resource_ids']: item['resource_ids'].append(rid); item['deep_resource_ids'].append(rid)
    reviewed_groups=review_groups(review)
    for item in items.values():
        if not item['id'].startswith('fanout:'): continue
        group=next((g for g in reviewed_groups if g['track']==item['track'] and item.get('module') in g.get('source_modules',[])),None)
        if group and urlparse(item.get('url','')).hostname in {'fanout.sh','www.fanout.sh'}: apply_resource_group(item,group,res)
    for (source,module,track),child_ids in sorted(groups.items()):
        topic_id='topic:fanout-'+slug(urlparse(source).path.strip('/')+'-'+module)
        if topic_id in items: topic_id+='-'+hashlib.sha256((source+module).encode()).hexdigest()[:8]
        topic=add(make_item(topic_id,'topic',module,track,res,placement='reference',module=module,related_ids=list(dict.fromkeys(child_ids)),source_urls=[source],summary='Independent study focus: '+module+'. These public topic titles form a coverage checklist; choose references within existing blocks.'))
        group=next((g for g in reviewed_groups if g['track']==track and module in g.get('source_modules',[])),None)
        if group: apply_resource_group(topic,group,res)
    for group in reviewed_groups:
        children=[i['id'] for i in items.values() if i['id'].startswith('fanout:') and i['track']==group['track'] and i.get('module') in group.get('source_modules',[])]
        urls=list(dict.fromkeys(u for child in children for u in items[child]['source_urls']))
        topic=add(make_item('topic:fanout-'+group['track']+'-'+slug(group['topic']),'topic',group['topic'],group['track'],res,placement='reference',source_modules=group.get('source_modules',[]),related_ids=children,source_urls=urls or [res[r]['url'] for r in group.get('primary_resource_ids',[]) if r in res],summary='Independent study objective: '+group['objective']))
        apply_resource_group(topic,group,res)
    stopwords={'the','and','for','with','one','from','data','using','design','system','systems','model','models','explain','week','study','read','project','basic','introduction','what','how','of','to','in','a','an','or'}
    tokens=lambda title:{w for w in re.findall(r'[a-z0-9]+',title.lower()) if len(w)>3 and w not in stopwords}
    source_items=[i for i in items.values() if i['id'].startswith('fanout:')]
    for item in list(items.values()):
        if item['placement']!='core' or item['kind'] not in {'systems','ai','exercise','project'}: continue
        title_words=tokens(item['title'])
        matches=[source for source in source_items if source['track'] in ({'ai','math','inference'} if item['track'] in {'ai','math'} else {item['track']}) and len(title_words & tokens(source['title']))>=2]
        item['related_ids']=list(dict.fromkeys(item['related_ids']+[s['id'] for s in matches]))
        for source in matches:
            source['related_ids'].append(item['id'])
        candidates=[g for g in reviewed_groups if g['track'] in ({'ai','math','inference'} if item['track'] in {'ai','math'} else {item['track']})]
        if candidates:
            scores=[(len(tokens(item['title']+' '+item.get('task','')) & tokens(g['topic']+' '+' '.join(g.get('source_modules',[])))),g) for g in candidates]
            score,group=max(scores,key=lambda entry:entry[0])
            if score>=2: apply_resource_group(item,group,res)
    for recommendation in review.get('project_space_review',{}).get('recommended_prerequisite_links',[]):
        project=items.get('project:'+recommendation['project_id'])
        if not project: continue
        project['prerequisite_notes']=recommendation.get('why','')
        start=min(a['day'] for a in project['assignments'])
        for raw in recommendation.get('recommended_before_or_with',[]):
            pid='exercise:'+raw if raw.startswith('E') and raw[1:].isdigit() else 'project:'+raw
            prerequisite=items.get(pid)
            if prerequisite and prerequisite['assignments'] and min(a['day'] for a in prerequisite['assignments'])<start:
                project['prerequisites'].append(pid)
        project['prerequisites']=list(dict.fromkeys(project['prerequisites']))
    for item in items.values():
        item['assigned_days']=sorted({a['day'] for a in item.get('assignments',[])})
        item['prerequisite_ids']=list(item.get('prerequisites',[]))
    catalog={'version':VERSION,'base_plan':copy.deepcopy(base_plan),'resources':resources,'items':list(items.values()),'source_inventory':source_inventory,'source_counts':{'captured_entries':sum(s['item_count'] for s in source_inventory),'unique_source_items':len(source_items),'captures':len(source_inventory)},'review':copy.deepcopy(review),'generation_rule':'Only explicit core assignments affect study slots. Captured public metadata and topic groups are reference-only. Historical progress is stored separately.','bootstrap_notes':{'original_version':base_plan['plan_meta'].get('version'),'candidate_profile':copy.deepcopy(base_plan.get('candidate_profile',{}))}}
    compile_catalog(catalog)
    return catalog

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--root',type=Path,default=ROOT); parser.add_argument('--check',action='store_true'); args=parser.parse_args()
    destination=args.root/'data/curriculum.json'
    if destination.exists():
        existing=json.loads(destination.read_text(encoding='utf-8-sig')); base=existing['base_plan']
    else: base=json.loads((args.root/'data/plan.json').read_text(encoding='utf-8-sig'))
    inventory_path=args.root/'reports/fanout-plan/public_inventory.json'; review_path=args.root/'reports/curriculum-review.json'
    inventory=json.loads(inventory_path.read_text(encoding='utf-8-sig')) if inventory_path.exists() else []
    review=json.loads(review_path.read_text(encoding='utf-8-sig')) if review_path.exists() else {}
    catalog=consolidate(base,inventory,review)
    if args.check: print('Catalog compiles: '+str(len(catalog['items']))+' items; no writes.'); return
    destination.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Created canonical curriculum: '+str(len(catalog['items']))+' items. Run build_curriculum.py to generate outputs.')

if __name__=='__main__': main()
