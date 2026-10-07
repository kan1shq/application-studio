"""Deterministic curriculum compilation. Importing this module performs no I/O."""
from __future__ import annotations
import argparse
import copy
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='3.0-unified'
BLOCKS={'dsa':0,'coding':0,'systems':1,'system':1,'design':1,'ai':2,'math':2,'career':3}

def normalize_plan(base):
    plan=copy.deepcopy(base)
    weeks={w['week']:w for w in plan['weeks']}
    for day in plan['days']:
        week=weeks[day['week']]
        day['project_id']=day.get('project_id') or week.get('project_id') or next((p['id'] for p in plan['projects'] if p['name']==day.get('project')),None)
        if not day['project_id']: raise ValueError('Missing project for day '+str(day['day']))
        day['plan_revision']=VERSION
    first=plan['days'][0]
    if first['day']==1 and [t['minutes'] for t in first['core_tasks']]==[75,45,45,15]:
        first['core_tasks'][0]['minutes']=60
        first['core_tasks'][0]['task']=first['core_tasks'][0]['task'].replace('55m for new attempts','40m for new attempts')
        first['core_tasks'][2]['minutes']=60
        donor=next(d for d in plan['days'] if d['week']==first['week'] and d.get('ai_theory'))
        first['ai_theory']=copy.deepcopy(donor['ai_theory'])
        lesson=weeks[first['week']].get('lessons',[''])[0]
        first['core_tasks'][2]['task']=f"AI theory (25m): {first['ai_theory']['subtext']} Project preparation (35m): {lesson}. Stop at the timebox."
        first['core_tasks'][2]['done_when']='One explanation or diagram plus one project-preparation observation; no foundational model training required.'
        first['learning_note']='Three focused hours: coding, systems, AI and career preparation. Exercises replace part of these blocks.'
    plan.setdefault('plan_meta',{}).update(version=VERSION,name='Unified systems, coding and modern AI curriculum')
    plan['learning_library']['version']=VERSION
    return plan

def compile_catalog(catalog):
    """Return a fresh plan derived only from the supplied catalog; never consult state."""
    plan=normalize_plan(catalog['base_plan'])
    days={d['day']:d for d in plan['days']}
    items={i['id']:i for i in catalog['items']}
    resources={r['id']:r for r in catalog['resources']}
    for d in days.values():
        for task in d['core_tasks']: task['item_ids']=[]
    exercise_totals=defaultdict(int)
    for item in catalog['items']:
        for assignment in item.get('assignments',[]):
            day=days.get(assignment['day']); block=assignment['block']
            if not day or type(block) is not int or not 0<=block<len(day['core_tasks']): raise ValueError('Invalid item assignment '+item['id'])
            task=day['core_tasks'][block]
            if item['id'] not in task['item_ids']: task['item_ids'].append(item['id'])
            if item['kind']=='exercise':
                minutes=assignment['minutes']
                if type(minutes) is not int or minutes<=0: raise ValueError('Invalid exercise minutes')
                exercise_totals[(day['day'],block)]+=minutes
                task['task']+=f" Within this block spend {minutes}m on {item['title']}: {item.get('task','')} This replaces part of this block's study or preparation; it adds no minutes."
                if assignment.get('replace_note'): task['task']+=' '+assignment['replace_note']
                task.setdefault('exercise_assignments',[]).append({'item_id':item['id'],'minutes':minutes})
                task.setdefault('exercise_minutes',0); task['exercise_minutes']+=minutes
        for resource in item.get('resource_ids',[]):
            if resource not in resources: raise ValueError('Unknown resource '+resource)
        for prerequisite in item.get('prerequisites',[]):
            if prerequisite not in items: raise ValueError('Unknown prerequisite '+prerequisite)
        for related in item.get('related_ids',[]):
            if related not in items: raise ValueError('Unknown related item '+related)
    for (day,block),minutes in exercise_totals.items():
        if minutes>days[day]['core_tasks'][block]['minutes']: raise ValueError(f'Exercises exceed day {day} block {block}')
    for d in days.values():
        if sum(t['minutes'] for t in d['core_tasks'])!=180: raise ValueError('Daily budget must be 180 minutes')
        if any(not t['item_ids'] for t in d['core_tasks']): raise ValueError('Unmapped task on day '+str(d['day']))
    for week in range(1,21):
        if sum(d['budget_minutes'] for d in days.values() if d['week']==week)!=1260: raise ValueError('Weekly budget must be 1260 minutes')
    plan['learning_library']['resources']=copy.deepcopy(catalog['resources'])
    plan['learning_library']['exercises']=[dict(copy.deepcopy(i),id=i['exercise_id'],catalog_item_id=i['id']) for i in catalog['items'] if i['kind']=='exercise' and i.get('exercise_id')]
    plan['learning_library']['checkpoints']=[copy.deepcopy(i) for i in catalog['items'] if i['kind']=='checkpoint']
    plan['curriculum']={'version':catalog['version'],'item_count':len(items),'core_count':sum(i['placement']=='core' for i in items.values()),'reference_count':sum(i['placement']=='reference' for i in items.values()),'unavailable_count':sum(i['placement']=='unavailable' for i in items.values()),'source_inventory':copy.deepcopy(catalog.get('source_inventory',[])),'source_counts':copy.deepcopy(catalog.get('source_counts',{}))}
    return plan

def render_daily(plan,last_day):
    lines=[f'# {last_day}-day unified study plan','',f"Generated from canonical curriculum {VERSION}. 180 minutes per day; 1,260 per week. Optional references replace study within a block. Day 70 is an evidence checkpoint, not a guaranteed outcome.",'']
    for d in plan['days'][:last_day]:
        lines += [f"## Day {d['day']} · Week {d['week']}: {d['title']}",'',f"Project: `{d['project_id']}`. Budget: {d['budget_minutes']} minutes.",'']
        for t in d['core_tasks']:
            lines += [f"- **{t['minutes']}m** {t['task']}",f"  Evidence: {t.get('done_when','Record honest completion evidence.')}",f"  Catalog IDs: {', '.join('`'+i+'`' for i in t['item_ids'])}"]
        lines += ['',f"Minimum: {d['minimum_action']}",'']
    return '\n'.join(lines)+'\n'

def render_interview(plan):
    c=plan['interview_curriculum']
    lines=['# Unified interview curriculum','',c.get('positioning',''),'',c.get('question_policy',''),'',c.get('difficulty',''),'',c.get('ddia_rule',''),'','## Shared readiness evidence','', 'At day 70: three independent coding mocks, three design mocks scored with the 0–20 rubric, six ownership stories and two explainable projects. Evidence must distinguish hints, AI assistance and measured outcomes.','']
    for w in plan['weeks']:
        lines += [f"## Week {w['week']}: {w['dsa_topic']}",'',f"Project: {w['project']}",'']
        lines += [f"- [LC {q['id']}: {q['title']}]({q['url']}) — {q['difficulty']} (`dsa:lc-{q['id']}`)" for q in w.get('questions',[])]
        lines += ['', 'System design:']+[f"- {t}" for t in w.get('system_topics',[])]+['',f"Friday mock: {w['design_prompt']}",f"Reading: {w['ddia']}",'']
    for checkpoint in plan['learning_library']['checkpoints']:
        lines += [f"## Day {checkpoint['day']}: {checkpoint['title']}",'']+['- '+x for x in checkpoint['criteria']]+['', 'Evidence IDs: '+', '.join(checkpoint.get('evidence_ids',[])),'']
    lines += ['## Evidence sources','']+[f"- [{s['title']}]({s['url']}): {s.get('takeaway','')}" for s in c.get('sources',[])]
    return '\n'.join(lines)+'\n'

def render_crosswalk(catalog):
    lines=['# Curriculum item crosswalk','','Generated from the canonical catalog. Public source titles are coverage references; independent study objectives are ours. Paid lesson bodies are neither retrieved nor reconstructed.','','| Item | Kind | Placement | Study assignment | Primary / optional deep reference |','|---|---|---|---|---|']
    for i in catalog['items']:
        assignments=', '.join(f"D{a['day']} B{a['block']+1}" for a in i.get('assignments',[])) or 'Reference only'
        safe=lambda s:str(s).replace('|','\\|').replace('\n',' ')
        lines.append(f"| {safe(i['id'])}: {safe(i['title'])} | {safe(i['kind'])} | {i['placement']} | {assignments} | {safe(i.get('primary_resource_id',''))} / {safe(', '.join(i.get('deep_resource_ids',[])))} |")
    return '\n'.join(lines)+'\n'

def render_html(catalog,plan):
    esc=lambda value:html.escape(str(value),quote=True)
    counts=Counter(i['kind'] for i in catalog['items'])
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unified learning curriculum</title><style>body{background:#111820;color:#e7edf4;font:16px system-ui;max-width:1200px;margin:auto;padding:32px}h1,h2{color:#b7e4d6}a{color:#9cd8ee}p{line-height:1.6}table{width:100%;border-collapse:collapse;margin:24px 0}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #2b3947}details{padding:14px;margin:12px 0;background:#192430;border-radius:10px}summary{cursor:pointer}input,select{background:#233341;color:white;border:0;padding:12px;margin:8px;border-radius:7px}code{overflow-wrap:anywhere}small{color:#aac0ce}.hidden{display:none}</style><h1>One curriculum, one evidence trail</h1><nav aria-label="Curriculum sections"><a href="#schedule">Schedule</a> · <a href="#catalog">Searchable catalog</a> · <a href="#coverage">Source coverage</a></nav>',f'<p>{len(plan["days"])} study days · {len(plan["projects"])} projects · {sum(len(w.get("questions",[])) for w in plan["weeks"])} coding questions · 21 hours per week</p>',f'<p>Catalog {esc(catalog["version"])}. '+esc(' · '.join(f'{n} {k}' for k,n in sorted(counts.items())))+'</p>','<p>Basic ML and deep learning remain theory. Projects use pretrained models and existing libraries. Public course titles identify coverage; study objectives are independently written. Optional references fit inside the listed blocks.</p>']
    coverage=catalog.get('source_counts',{})
    captures=catalog.get('source_inventory',[])
    parts += ['<section id="coverage"><h2>Source coverage</h2>',f'<p>{coverage.get("captures",len(captures))} captured public pages · {coverage.get("captured_entries",sum(c.get("item_count",0) for c in captures))} metadata entries · {coverage.get("unique_source_items",0)} unique source items. Repeated links can appear in several directories and course outlines.</p>','<p>Directory captures may be incomplete where pagination, filters or access limits apply. Mathematics roadmap placeholders and advertised totals can differ from the named public steps; generic or hidden labels are retained as coverage notes and do not become invented lessons or extra assignments. Announced courses remain unavailable until readable material exists.</p><details><summary>Captured pages and coverage notes</summary><ul>']
    for capture in captures:
        notes=capture.get('notes',[])
        if isinstance(notes,str): notes=[notes]
        parts.append(f'<li><a href="{esc(capture["source_url"])}">{esc(capture["source_url"])}</a> — {capture.get("item_count",0)} entries; '+('complete capture' if capture.get('complete') else 'partial capture')+(' · '+esc('; '.join(map(str,notes))) if notes else '')+'</li>')
    parts += ['</ul></details></section><h2 id="schedule">Schedule</h2><table><thead><tr><th>Week / day</th><th>Session</th><th>Blocks and catalog links</th></tr></thead><tbody>']
    for d in plan['days']:
        blocks=''.join(f'<p><b>{t["minutes"]}m</b> {esc(t["task"])}<br><small>'+', '.join(f'<a href="#{esc(i)}">{esc(i)}</a>' for i in t['item_ids'])+'</small></p>' for t in d['core_tasks'])
        parts.append(f'<tr><td>W{d["week"]} / D{d["day"]}</td><td>{esc(d["title"])}<br><small>{esc(d["project_id"])}</small></td><td>{blocks}</td></tr>')
    parts += ['</tbody></table><h2 id="catalog">Searchable catalog</h2><input id="search" placeholder="Search titles, modules, IDs"><select id="placement"><option value="">All placements</option><option>core</option><option>reference</option><option>unavailable</option></select><select id="kind"><option value="">All kinds</option>']+[f'<option>{esc(k)}</option>' for k in sorted(counts)]+['</select>']
    resources={r['id']:r for r in catalog['resources']}
    for i in catalog['items']:
        assignment=', '.join(f"Day {a['day']} / block {a['block']+1}" for a in i.get('assignments',[])) or 'Reference only; no additional scheduled work'
        links=' · '.join(f'<a href="{esc(resources[r]["url"])}" target="_blank" rel="noreferrer">{esc(r)}: {esc(resources[r]["title"])}</a>' for r in i.get('resource_ids',[]))
        source=' · '.join(f'<a href="{esc(u)}" target="_blank" rel="noreferrer">Public source</a>' for u in i.get('source_urls',[]))
        relations=', '.join(f'<a href="#{esc(r)}">{esc(r)}</a>' for r in i.get('related_ids',[]))
        outline=''
        if i.get('public_outline'): outline='<p><b>Public outline headings</b></p><ul>'+''.join('<li>'+esc(h)+'</li>' for h in i['public_outline'])+'</ul>'
        parts.append(f'<details class="item" id="{esc(i["id"])}" data-kind="{esc(i["kind"])}" data-placement="{i["placement"]}"><summary>{esc(i["title"])} <small>· {esc(i["kind"])} · {i["placement"]}</small></summary><p><code>{esc(i["id"])}</code><br>{esc(assignment)}</p><p>{esc(i.get("summary",i.get("task","")))}</p>{outline}<p>{links}</p><p>{source}</p><p>{relations}</p></details>')
    parts += ['<script>const inputs=[document.querySelector("#search"),document.querySelector("#placement"),document.querySelector("#kind")];function filter(){const[q,p,k]=inputs.map(x=>x.value.toLowerCase());document.querySelectorAll(".item").forEach(x=>x.classList.toggle("hidden",(p&&x.dataset.placement!==p)||(k&&x.dataset.kind!==k)||(q&&!x.textContent.toLowerCase().includes(q))))}inputs.forEach(x=>x.addEventListener("input",filter));window.addEventListener("hashchange",()=>{let x=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(x&&x.tagName==="DETAILS"){x.open=true;x.classList.remove("hidden")}});</script></html>']
    return '\n'.join(parts)

def outputs(catalog):
    plan=compile_catalog(catalog)
    page=render_html(catalog,plan)
    return {'data/plan.json':json.dumps(plan,ensure_ascii=False,indent=2)+'\n','reports/140_DAY_PLAN.md':render_daily(plan,140),'reports/70_DAY_PLAN.md':render_daily(plan,70),'reports/INTERVIEW_CURRICULUM.md':render_interview(plan),'reports/CURRICULUM_CROSSWALK.md':render_crosswalk(catalog),'reports/fanout-plan/learning-library-plan.html':page,'dist/learning-library-plan.html':page}

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--root',type=Path,default=ROOT); parser.add_argument('--check',action='store_true'); args=parser.parse_args()
    catalog=json.loads((args.root/'data/curriculum.json').read_text(encoding='utf-8-sig'))
    artifacts=outputs(catalog)
    if args.check:
        stale=[p for p,data in artifacts.items() if not (args.root/p).exists() or (args.root/p).read_text(encoding='utf-8-sig')!=data]
        if stale: raise SystemExit('Stale generated outputs: '+', '.join(stale))
        print('All generated curriculum outputs are current.'); return
    for name,data in artifacts.items():
        path=args.root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(data,encoding='utf-8')
    print('Built '+str(len(artifacts))+' deterministic curriculum artifacts.')

if __name__=='__main__': main()
