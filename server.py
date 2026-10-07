"""Local application workspace. Python standard library only; binds to loopback."""
from __future__ import annotations
import argparse, csv, hashlib, html, io, json, re, sqlite3, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from types import SimpleNamespace
import linkedin_search
import learning_store
import resume_studio

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DB_PATH = DATA / 'workspace.sqlite'
STATUSES = {'New', 'Shortlisted', 'Researching', 'Applied', 'Interviewing', 'Offer', 'Rejected', 'Passed'}
REFRESH_LOCK = threading.Lock()
REFRESH = {'running': False, 'completed': 0, 'total': 0, 'message': 'Ready'}
SKILLS = {'Python': r'\bpython\b', 'Java': r'\bjava\b', 'Go': r'\bgolang\b|\bgo language\b', 'SQL/Postgres': r'\bsql\b|postgres', 'Kafka': r'kafka', 'Kubernetes': r'kubernetes|\baks\b|\bk8s\b', 'Azure': r'azure', 'AWS': r'\baws\b|amazon web services', 'LLM': r'\bllms?\b|large language model', 'Evaluation': r'evaluation|evals|benchmark', 'RAG': r'\brag\b|retrieval.augmented', 'TypeScript/React': r'typescript|react', 'Distributed systems': r'distributed systems', 'Observability': r'observability|monitoring|tracing', 'CI/CD': r'ci/cd|continuous integration'}

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def read_json(name, default):
    path = DATA / name
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()

def initialize():
    DATA.mkdir(exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, source_id TEXT, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source_id);
        CREATE TABLE IF NOT EXISTS job_state (id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'New', notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS prep_state (day INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS source_state (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS linkedin_searches (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL);
        ''')
        learning_store.initialize(db)
        for job in read_json('jobs_seed.json', {'jobs': []}).get('jobs', []):
            db.execute('INSERT OR IGNORE INTO jobs VALUES (?,?,?)', (job['id'], job['source_id'], json.dumps(job)))

def textify(value):
    value = html.unescape(html.unescape(str(value or '')))
    value = re.sub(r'<(?:br\s*/?|/p|/li|/div)>', '\n', value, flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>', '', value)).strip()

def region_of(location):
    s = location.lower()
    if any(city in s for city in ['stuttgart','augsburg','cologne','frankfurt','dusseldorf','düsseldorf','dresden','leipzig','karlsruhe','nuremberg','nürnberg','darmstadt']): return 'EU', 'Germany', 0
    countries = [('Germany', ['germany','berlin','munich','hamburg']), ('Netherlands', ['netherlands','amsterdam','rotterdam']), ('France',['france','paris','lyon']), ('Italy',['italy','milan','milano']), ('Spain',['spain','madrid','barcelona']), ('Ireland',['ireland','dublin']), ('Sweden',['sweden','stockholm']), ('Denmark',['denmark','copenhagen']), ('Finland',['finland','helsinki']), ('Poland',['poland','warsaw','krakow']), ('Portugal',['portugal','lisbon','porto']), ('Austria',['austria','vienna']), ('Belgium',['belgium','brussels']), ('Czechia',['czech','prague']), ('Estonia',['estonia','tallinn']), ('Lithuania',['lithuania','vilnius']), ('Latvia',['latvia','riga']), ('Romania',['romania','bucharest']), ('Greece',['greece','athens']), ('Luxembourg',['luxembourg']), ('Bulgaria',['bulgaria','sofia']), ('Croatia',['croatia','zagreb']), ('Hungary',['hungary','budapest']), ('Slovakia',['slovakia','bratislava']), ('Slovenia',['slovenia','ljubljana']), ('Malta',['malta']), ('Cyprus',['cyprus'])]
    for country, words in countries:
        if any(w in s for w in words): return 'EU', country, 0
    for country, words in [('Singapore',['singapore']),('Indonesia',['indonesia','jakarta']),('Japan',['japan','tokyo']),('South Korea',['south korea','seoul']),('Taiwan',['taiwan','taipei']),('Hong Kong',['hong kong']),('Vietnam',['vietnam','ho chi minh','hanoi']),('Thailand',['thailand','bangkok']),('Malaysia',['malaysia','kuala lumpur'])]:
        if any(w in s for w in words): return 'Asia', country, 1
    for city, words, rank in [('Bangalore',['bengaluru','bangalore'],2),('Hyderabad',['hyderabad'],3),('Mumbai',['mumbai'],4),('Pune',['pune'],5)]:
        if any(w in s for w in words): return city, 'India', rank
    if 'india' in s: return 'India · location unspecified', 'India', 6
    if any(w in s for w in ['europe','emea','remote anywhere','worldwide']): return 'Remote · eligibility unconfirmed', 'Unconfirmed', 7
    return 'Other', 'Unconfirmed', 9

def relevant(title, location):
    return bool(re.search(r'engineer|developer', title, re.I)) and not re.search(r'intern|manager|director|principal|staff|sales|support|solutions|hardware|embedded|qa engineer|test engineer', title, re.I) and region_of(location)[2] < 9

def fetch_json(url):
    req = Request(url, headers={'User-Agent': 'ApplicationStudio/1.0 (personal job research)', 'Accept': 'application/json'})
    with urlopen(req, timeout=25) as response:
        if response.status != 200: raise RuntimeError(f'HTTP {response.status}')
        return json.load(response)

def fetch_board(source):
    provider, board = source['provider'].lower(), quote(source['board'], safe='')
    if provider == 'ashby':
        url = f'https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true'
        body = fetch_json(url)
        if not isinstance(body.get('jobs'), list): raise ValueError('Unexpected Ashby response')
        jobs = []
        for j in body['jobs']:
            if j.get('isListed') is False: continue
            compensation = j.get('compensation') or {}
            salary = compensation.get('compensationTierSummary') or compensation.get('scrapeableCompensationSalarySummary') or 'Not published in structured feed'
            jobs.append({'external_id': j.get('id') or j['jobUrl'].rstrip('/').split('/')[-1], 'title': j['title'], 'location': ', '.join(dict.fromkeys([j.get('location','')] + [l.get('location','') for l in j.get('secondaryLocations', []) if isinstance(l,dict)])), 'apply_url': j.get('applyUrl') or j['jobUrl'], 'source_url': j['jobUrl'], 'description': j.get('descriptionPlain') or textify(j.get('descriptionHtml')), 'posted_at': j.get('publishedAt'), 'salary_feed': salary, 'workplace_type': j.get('workplaceType', ''), 'department': j.get('department', '')})
    elif provider == 'greenhouse':
        url = f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true'
        body = fetch_json(url)
        if not isinstance(body.get('jobs'), list): raise ValueError('Unexpected Greenhouse response')
        jobs = [{'external_id': str(j['id']), 'title': j['title'], 'location': j.get('location',{}).get('name',''), 'apply_url': j['absolute_url'], 'source_url': j['absolute_url'], 'description': textify(j.get('content')), 'posted_at': j.get('updated_at'), 'salary_feed':'Not published in structured feed'} for j in body['jobs']]
    elif provider == 'lever':
        url = f'https://api.lever.co/v0/postings/{board}?mode=json'
        body = fetch_json(url)
        if not isinstance(body, list): raise ValueError('Unexpected Lever response')
        jobs = [{'external_id': j['id'], 'title': j['text'], 'location': j.get('categories',{}).get('location',''), 'apply_url': j['applyUrl'], 'source_url': j['hostedUrl'], 'description': textify(j.get('descriptionPlain') or j.get('description','')) + '\n' + '\n'.join(textify(x.get('content')) for x in j.get('lists',[])), 'posted_at': None, 'salary_feed': str(j.get('salaryDescription') or 'Not published in structured feed')} for j in body]
    else: raise ValueError('Supported providers: Ashby, Greenhouse, Lever')
    return jobs, url

def refresh_source(source):
    timestamp = now()
    try:
        feed, url = fetch_board(source)
        with connect() as db:
            previous = {row['id']: json.loads(row['payload']) for row in db.execute('SELECT id,payload FROM jobs WHERE source_id=?', (source['id'],))}
            seen, added, matched = set(), 0, 0
            for raw in feed:
                jid = f"{source['id']}:{raw['external_id']}"
                seen.add(jid)
                if jid not in previous and not relevant(raw['title'], raw['location']): continue
                matched += 1
                old = previous.get(jid, {})
                reg, country, rank = region_of(raw['location'])
                detected_skills=[k for k,v in SKILLS.items() if re.search(v,raw['description'],re.I)]
                fingerprint=hashlib.sha256(re.sub(r'\s+',' ',raw['description']).encode()).hexdigest()
                experience_signals=list(dict.fromkeys(re.findall(r'\b\d+(?:\s*[-–]\s*\d+)?\+?\s+years',raw['description'],flags=re.I)))[:5]
                new = dict(old)
                new.update(raw)
                new.update(full_description=raw['description'], jd_checked_at=timestamp,
                           jd_source_url=url)
                new.update(id=jid, source_id=source['id'], company=source['company'], region=reg, country=country, location_rank=rank, status_source='active', verified_at=timestamp, last_seen=timestamp, verification_method='Public ATS API', verification_source=url, first_seen=old.get('first_seen',timestamp), skills=detected_skills)
                new['description']='Topics detected in the posting (not validated must-haves): '+', '.join(detected_skills)+'. Experience phrases: '+(', '.join(experience_signals) or 'not detected')+'. Read the official listing for full requirements and context.'
                if old.get('feed_title') and (old['feed_title'] != raw['title'] or old.get('feed_location') != raw['location'] or (old.get('description_hash') and old['description_hash']!=fingerprint)):
                    new.update(fit_band='Needs review', fit_reasons='Listing changed since its previous review.', gaps='Recheck requirements, pay and eligibility.', reviewed=False)
                new.update(feed_title=raw['title'],feed_location=raw['location'],description_hash=fingerprint)
                if not old:
                    added += 1
                    new.update(fit_band='Needs review', fit_reasons='New live opening matched the title/location filter; resume fit has not been reviewed.', gaps='Review full requirements, experience, pay and work authorization.', reviewed=False, role_track='AI' if re.search(r'\bAI\b|machine learning|LLM', raw['title'], re.I) else 'Backend / product', requirements='Detected topics, not a requirement assessment: '+', '.join(detected_skills), years_required='Check full posting', salary_text=raw['salary_feed'], visa_text='Unknown — check with recruiter', visa_evidence_url='', company_mission=source.get('company_mission',''), founder_or_funding_evidence=source.get('founder_or_funding_evidence',''))
                db.execute('INSERT INTO jobs VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (jid, source['id'], json.dumps(new)))
            for jid, old in previous.items():
                if jid not in seen:
                    old.update(status_source='not_listed', verified_at=timestamp, verification_method='Absent from successful complete ATS feed')
                    db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(old),jid))
            result = {'id':source['id'], 'ok':True, 'checked_at':timestamp, 'feed_count':len(feed), 'matching_count':matched, 'new_count':added, 'url':url, 'message':'Verified against current feed'}
            db.execute('INSERT OR REPLACE INTO source_state VALUES (?,?)', (source['id'],json.dumps(result)))
        return result
    except Exception as exc:
        result = {'id':source['id'], 'ok':False, 'checked_at':timestamp, 'message':f'{type(exc).__name__}: {exc}. Existing jobs retained; last successful verification remains on each job.'}
        with connect() as db: db.execute('INSERT OR REPLACE INTO source_state VALUES (?,?)', (source['id'],json.dumps(result)))
        return result

def refresh_all():
    sources = [s for s in read_json('sources.json', []) if s.get('enabled',True)]
    REFRESH.update(running=True, completed=0,total=len(sources),message='Checking official job boards…')
    try:
        results=[]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(refresh_source,s) for s in sources if s.get('enabled',True)]
            for f in as_completed(futures):
                result=f.result(); results.append(result)
                REFRESH.update(completed=len(results),message=f"Checked {len(results)} of {len(futures)} boards")
        REFRESH.update(message=f"Finished: {sum(r['ok'] for r in results)}/{len(results)} boards succeeded. Failed sources keep their previous data.", finished_at=now())
    finally:
        REFRESH['running']=False
        REFRESH_LOCK.release()

def linkedin_context():
    return SimpleNamespace(connect=connect,region_of=region_of)

def snapshot():
    with connect() as db:
        jobs=[]
        for row in db.execute('SELECT j.payload, s.status, s.notes, s.updated_at FROM jobs j LEFT JOIN job_state s ON s.id=j.id'):
            j=json.loads(row['payload']); j.update(application_status=row['status'] or 'New', notes=row['notes'] or '', user_updated_at=row['updated_at']); jobs.append(j)
        prep={str(r['day']):json.loads(r['payload']) for r in db.execute('SELECT day,payload FROM prep_state')}
        health={r['id']:json.loads(r['payload']) for r in db.execute('SELECT id,payload FROM source_state')}
        learning=learning_store.view(db,read_json('curriculum.json',{'items':[]}))
    plan=read_json('plan.json',{})
    plan['days']=[learning['sessions'].get(str(d['day']),{}).get('definition',d) for d in plan.get('days',[])]
    return {'jobs':jobs,'prep_state':prep,'learning':learning,'curriculum':read_json('curriculum.json',{'version':1,'items':[]}),'sources':[dict(s,health=health.get(s['id'])) for s in read_json('sources.json',[])], 'discovery':read_json('discovery.json',{}), 'plan':plan,'analysis':read_json('analysis.json',{}),'companies':read_json('companies.json',{}),'refresh':dict(REFRESH),'linkedin':linkedin_search.view(linkedin_context()),'generated_at':now()}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
    def log_message(self,fmt,*args): print(fmt % args, flush=True)
    def send_json(self,data,status=200):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8'); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def do_GET(self):
        if not self.valid_host(): return self.send_json({'error':'Local host required'},403)
        path=urlparse(self.path).path
        if path=='/api/health': return self.send_json({'app':'application-studio','ok':True,'root':str(ROOT)})
        if path=='/api/state': return self.send_json(snapshot())
        if path=='/api/resume/profile': return self.send_json({'profile':resume_studio.load_profile(DATA)})
        if path=='/api/resume/gaps':
            profile=resume_studio.load_profile(DATA)
            if not profile: return self.send_json({'error':'Save your full resume profile first'},400)
            return self.send_json(resume_studio.gap_report(profile,snapshot()['jobs']))
        if path=='/api/curriculum/catalog': return self.send_json(read_json('curriculum.json',{'version':1,'items':[]}))
        if path=='/api/refresh-status': return self.send_json(dict(REFRESH))
        if path=='/api/linkedin/status': return self.send_json(linkedin_search.view(linkedin_context()))
        if path=='/api/export': return self.send_json(snapshot())
        if path=='/api/jobs.csv':
            fields=['company','title','location','country','fit_band','salary_text','visa_text','years_required','requirements','gaps','application_status','notes','status_source','verified_at','source_url','apply_url']
            out=io.StringIO(newline=''); writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore'); writer.writeheader()
            for j in snapshot()['jobs']:
                row={k:str(j.get(k,'') or '') for k in fields}
                for k,v in row.items():
                    if v.startswith(('=','+','-','@')): row[k]="'"+v
                writer.writerow(row)
            body=('\ufeff'+out.getvalue()).encode('utf-8'); self.send_response(200); self.send_header('Content-Type','text/csv; charset=utf-8'); self.send_header('Content-Disposition','attachment; filename="jobs.csv"'); self.end_headers(); return self.wfile.write(body)
        if path.startswith('/api/'): return self.send_json({'error':'Not found'},404)
        return super().do_GET()
    def do_POST(self):
        origin=self.headers.get('Origin')
        allowed={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
        if not self.valid_host() or (origin and origin not in allowed): return self.send_json({'error':'Local origin required'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json': return self.send_json({'error':'JSON required'},415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            maximum=2000000 if self.path in ('/api/curriculum/import','/api/resume/profile') else 100000
            if length<0 or length>maximum: return self.send_json({'error':'Invalid request length'},413)
            body=json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body,dict): raise ValueError('JSON object required')
            if self.path=='/api/resume/profile':
                return self.send_json({'profile':resume_studio.save_profile(DATA,body.get('profile'))})
            if self.path in ('/api/resume/generate','/api/resume/jd','/api/resume/pdf'):
                jid=body.get('job_id')
                if not isinstance(jid,str): raise ValueError('Select a saved job')
                with connect() as db:
                    row=db.execute('SELECT payload FROM jobs WHERE id=?',(jid,)).fetchone()
                    if not row: raise ValueError('Unknown job')
                    job=json.loads(row['payload'])
                    if self.path=='/api/resume/jd':
                        jd=body.get('full_description')
                        if not isinstance(jd,str) or not 80<=len(jd)<=80000: raise ValueError('Paste a full JD of 80-80000 characters')
                        job.update(full_description=jd,jd_checked_at=now(),jd_source_url=job.get('source_url',''),jd_origin='user pasted')
                        db.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(job),jid))
                        return self.send_json({'saved':True})
                profile=resume_studio.load_profile(DATA)
                if not profile: raise ValueError('Save your full resume profile first')
                draft=resume_studio.generate(profile,job,body.get('max_bullets',4))
                if self.path=='/api/resume/pdf':
                    kind=body.get('kind')
                    if kind not in ('resume','cover_letter'):raise ValueError('Choose resume or cover_letter')
                    if any(body.get(k)!=draft['audit'][k] for k in ('profile_hash','jd_hash')):
                        return self.send_json({'error':'Your profile or JD changed. Generate the drafts again before downloading PDFs.'},409)
                    try:content=resume_studio.compile_pdf(draft[kind+'_tex'])
                    except RuntimeError as exc:return self.send_json({'error':str(exc)},503)
                    self.send_response(200);self.send_header('Content-Type','application/pdf');self.send_header('Content-Disposition','attachment; filename="'+kind.replace('_','-')+'.pdf"');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();return self.wfile.write(content)
                draft['pdf_request']={'job_id':jid,'max_bullets':body.get('max_bullets',4),'profile_hash':draft['audit']['profile_hash'],'jd_hash':draft['audit']['jd_hash']}
                return self.send_json(draft)
            learning_routes={'/api/learning/state':learning_store.save_state,'/api/learning/attempt':learning_store.attempt}
            curriculum_routes={'/api/curriculum/import':learning_store.import_snapshot,'/api/curriculum/refresh':learning_store.refresh,'/api/curriculum/adopt':learning_store.adopt}
            if self.path in learning_routes:
                with connect() as db: result=learning_routes[self.path](db,read_json('curriculum.json',{'items':[]}),body)
                return self.send_json(result)
            if self.path in curriculum_routes:
                with connect() as db: result=curriculum_routes[self.path](db,body)
                return self.send_json(result,502 if result.get('error') else 200)
            if self.path=='/api/shutdown':
                if REFRESH['running'] or linkedin_search.STATUS['running']: return self.send_json({'error':'Wait for the current search or refresh to finish before stopping.'},409)
                self.send_json({'stopping':True})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            if self.path=='/api/refresh':
                if not REFRESH_LOCK.acquire(blocking=False): return self.send_json({'running':True},202)
                REFRESH.update(running=True,completed=0,message='Starting refresh…')
                threading.Thread(target=refresh_all,daemon=True).start(); return self.send_json({'running':True},202)
            if self.path=='/api/linkedin/search':
                return self.send_json(linkedin_search.start(linkedin_context(),body),202)
            if self.path=='/api/linkedin/rematch':
                return self.send_json(linkedin_search.rematch(linkedin_context(),body))
            if self.path=='/api/linkedin/track':
                return self.send_json(linkedin_search.track(linkedin_context(),body.get('id')))
            if self.path=='/api/job-state':
                jid=body.get('id'); status=body.get('status','New'); notes=body.get('notes','')
                if status not in STATUSES or not isinstance(notes,str) or len(notes)>12000: raise ValueError('Invalid status or notes')
                with connect() as db:
                    if not db.execute('SELECT 1 FROM jobs WHERE id=?',(jid,)).fetchone(): raise ValueError('Unknown job')
                    db.execute('INSERT OR REPLACE INTO job_state VALUES (?,?,?,?)',(jid,status,notes,now()))
                return self.send_json({'saved':True})
            if self.path=='/api/prep-state':
                day=body.get('day'); state=body.get('state')
                valid_days={d['day'] for d in read_json('plan.json',{}).get('days',[])}
                if type(day) is not int or day not in valid_days or not isinstance(state,dict): raise ValueError('Invalid day/state')
                tasks=state.get('tasks',[]); notes=state.get('notes','')
                if not isinstance(tasks,list) or not all(type(x) is int and 0<=x<30 for x in tasks) or not isinstance(notes,str) or len(notes)>12000: raise ValueError('Invalid prep state')
                clean={'tasks':sorted(set(tasks)), 'notes':notes, 'minimum_done':state.get('minimum_done') is True, 'energy':state.get('energy','standard') if state.get('energy','standard') in ('minimum','standard','stretch') else 'standard'}
                with connect() as db:
                    learning_store.capture(db,day,clean,read_json('plan.json',{}))
                    db.execute('INSERT OR REPLACE INTO prep_state VALUES (?,?,?)',(day,json.dumps(clean),now()))
                return self.send_json({'saved':True})
            return self.send_json({'error':'Not found'},404)
        except learning_store.Conflict as exc: return self.send_json({'error':str(exc)},409)
        except (ValueError,TypeError,KeyError) as exc: return self.send_json({'error':str(exc)},400)
        except Exception: return self.send_json({'error':'Could not save. Your input remains on screen; retry.'},500)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8767); parser.add_argument('--refresh',action='store_true'); args=parser.parse_args(); initialize()
    if args.refresh:
        REFRESH_LOCK.acquire(); refresh_all(); print(json.dumps(REFRESH)); raise SystemExit(0)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Application studio: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
