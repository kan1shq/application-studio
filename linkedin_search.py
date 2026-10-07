"""Bounded LinkedIn public search. No account credentials, cookies or private APIs."""
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import json, re, threading, time
from datetime import datetime, timezone

LOCK = threading.Lock()
STATUS = {'running': False, 'message': 'Ready', 'completed': 0}
MAX_DETAILS = 8
COOLDOWN = 60
LAST_REQUEST = 0.0
DEFAULTS = {'query':'AI Engineer','location':'Bengaluru, Karnataka, India','posted':'week','remote':False,
            'keywords':'Python, LLM, RAG, agents','exclude':'intern, internship, staff, principal, director',
            'mode':'any','limit':100,'pages':5}
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

class Blocked(RuntimeError): pass

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def text(self):
        return ' '.join(x.text() if isinstance(x,Node) else x for x in self.children)
    def walk(self):
        yield self
        for x in self.children:
            if isinstance(x,Node):yield from x.walk()
    def has(self, cls):
        return cls in (self.attrs.get('class') or '').split()

class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root]
    def handle_starttag(self, tag, attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in VOID:self.stack.append(n)
    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag,attrs))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:
                del self.stack[i:];break
    def handle_data(self,data):
        if self.stack[-1].tag not in {'script','style'}:self.stack[-1].children.append(data)

def clean(text):
    return re.sub(r'\s+',' ',text).strip()

def job_id(url):
    if not isinstance(url,str):return None
    p=urlparse(url)
    if p.scheme not in ('http','https') or not (p.hostname=='linkedin.com' or (p.hostname or '').endswith('.linkedin.com')):return None
    m=re.search(r'/jobs/view/(?:[^/?]*-)?(\d+)(?:/|$)',p.path)
    return m.group(1) if m else None

def parse_cards(page):
    tree=Tree();tree.feed(page)
    jobs={}
    for card in tree.root.walk():
        urn=card.attrs.get('data-entity-urn','')
        m=re.fullmatch(r'urn:li:jobPosting:(\d+)',urn)
        if not m:continue
        fields={}
        for n in card.walk():
            for cls,key in [('base-search-card__title','title'),('base-search-card__subtitle','company'),('job-search-card__location','location')]:
                if n.has(cls):fields[key]=clean(n.text())
            if n.tag=='time':fields['posted_at']=n.attrs.get('datetime','')
        if fields.get('title'):
            ident=m.group(1);fields.update(id=ident,url='https://www.linkedin.com/jobs/view/'+ident+'/',scan_text='',detail_status='Not scanned')
            jobs[ident]=fields
    return list(jobs.values())

def parse_description(page):
    tree=Tree();tree.feed(page)
    nodes=list(tree.root.walk())
    for n in nodes:
        if n.has('show-more-less-html__markup') or n.has('description__text'):
            text=clean(n.text())
            if text:return text[:40000]
    return ''

def allowed_url(url):
    p=urlparse(url)
    path_ok=p.path.startswith('/jobs/') or p.path=='/jobs-guest/jobs/api/seeMoreJobPostings/search'
    return p.scheme=='https' and p.hostname in {'www.linkedin.com','linkedin.com','in.linkedin.com'} and path_ok and not p.username and not p.password

class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not allowed_url(newurl):raise Blocked('LinkedIn requires a sign-in/checkpoint or redirected outside public jobs. Search stopped; saved results retained.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_page(url):
    if not allowed_url(url):raise ValueError('Unsupported public jobs URL')
    try:
        req=Request(url,headers={'User-Agent':'ApplicationStudio/1.0 (personal job search)','Accept':'text/html'})
        with build_opener(SafeRedirect()).open(req,timeout=12) as response:
            body=response.read(2_000_001)
            if len(body)>2_000_000:raise ValueError('Public response exceeded the size limit')
            return body.decode('utf-8','replace')
    except HTTPError as e:
        if e.code in {401,403,429,999}:raise Blocked(f'LinkedIn returned HTTP {e.code}. Requests stopped; no login or retry workaround is attempted.') from None
        raise RuntimeError(f'LinkedIn returned HTTP {e.code}') from None
    except URLError:
        raise RuntimeError('Could not reach LinkedIn. Check the connection; previous results are retained.') from None
    except (TimeoutError,OSError):
        raise RuntimeError('LinkedIn request timed out or the connection closed. Fetched results are retained.') from None

def terms(value):
    return list(dict.fromkeys(clean(x) for x in value.split(',') if clean(x)))

def validate(body):
    if not isinstance(body,dict):raise ValueError('Search settings must be an object')
    out={}
    for key,maxlen in [('query',160),('location',160),('keywords',400),('exclude',300)]:
        value=body.get(key,DEFAULTS[key])
        if not isinstance(value,str) or len(value)>maxlen:raise ValueError('Invalid '+key)
        out[key]=clean(value)
    if not out['query'] or not out['location']:raise ValueError('Enter a search query and location')
    if len(terms(out['keywords']))>20 or len(terms(out['exclude']))>20:raise ValueError('Use at most 20 comma-separated terms')
    out['posted']=body.get('posted','week');out['mode']=body.get('mode','any');out['limit']=body.get('limit',100)
    out['pages']=body.get('pages',DEFAULTS['pages'])
    if out['posted'] not in {'day','week','month','any'} or out['mode'] not in {'any','all'}:raise ValueError('Invalid search filter')
    if type(out['limit']) is not int or out['limit'] not in {10,25,50,100,250}:raise ValueError('Choose 10, 25, 50, 100 or 250 results')
    if type(out['pages']) is not int or not 1<=out['pages']<=10:raise ValueError('Choose between 1 and 10 pages')
    out['remote']=body.get('remote') is True
    return out

def search_url(config,start=None):
    params={'keywords':config['query'],'location':config['location'],'sortBy':'DD'}
    if config['posted']!='any':params['f_TPR']={'day':'r86400','week':'r604800','month':'r2592000'}[config['posted']]
    if config['remote']:params['f_WT']='2'
    if start is not None:
        params['start']=start
        return 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?'+urlencode(params)
    return 'https://www.linkedin.com/jobs/search/?'+urlencode(params)

def collect_pages(config):
    jobs={};warnings=[];pages=[];offset=0;reason='page_limit';failed=False
    deadline=time.monotonic()+100
    for index in range(config['pages']):
        if time.monotonic()>deadline:
            reason='time_limit';warnings.append('Search time budget reached; fetched jobs retained.');break
        STATUS.update(message=f'Fetching page {index+1}/{config["pages"]}; {len(jobs)} unique jobs so far.')
        try:
            page=fetch_page(search_url(config,None if index==0 else offset))
            cards=parse_cards(page)
            empty=not page.strip() or bool(re.search(r'no matching jobs|no results found|no jobs found',clean(TreeText(page)),re.I))
            if not cards and not empty:raise Blocked('No readable job cards. LinkedIn may have changed the page or requires sign-in.')
        except (RuntimeError,ValueError) as e:
            if not pages:raise
            warnings.append(f'Page {index+1}: {e} Earlier pages retained; no further requests made.')
            reason='request_failed';failed=True;break
        before=len(jobs)
        for job in cards:
            if len(jobs)>=config['limit']:break
            jobs.setdefault(job['id'],job)
        pages.append({'page':index+1,'offset':offset,'cards':len(cards),'added':len(jobs)-before})
        if not cards:reason='end_of_results';break
        if len(jobs)==before:reason='no_new_jobs';break
        if len(jobs)>=config['limit']:reason='result_limit';break
        # Advance by the actual batch size: the first page and load-more batches differ.
        offset+=len(cards)
        if index+1<config['pages']:time.sleep(1)
    return list(jobs.values()),warnings,{'pages_fetched':len(pages),'pages':pages,'stop_reason':reason},failed

def contains(text,term):
    # Word boundaries keep Java distinct from JavaScript and Go from ongoing.
    pattern=r'(?<!\w)'+re.escape(term).replace(r'\ ',r'\s+')+r'(?!\w)'
    return bool(re.search(pattern,text,re.I))

def match(job,config):
    text=' '.join(job.get(k,'') for k in ['title','company','location','scan_text'])
    wanted=terms(config['keywords'])
    found=[t for t in wanted if contains(text,t)]
    excluded=[t for t in terms(config['exclude']) if contains(job.get('title',''),t)]
    passed=not wanted or (len(found)==len(wanted) if config['mode']=='all' else bool(found))
    status='excluded' if excluded else 'match' if passed else 'unknown' if not job.get('scan_text') else 'no_match'
    return dict(job,matched=found,not_found=[t for t in wanted if t not in found],excluded=excluded,
                match_status=status,keyword_count=len(found),coverage='Description + card' if job.get('scan_text') else 'Card only')

def latest(app):
    with app.connect() as db:
        row=db.execute('SELECT payload FROM linkedin_searches ORDER BY id DESC LIMIT 1').fetchone()
    return json.loads(row['payload']) if row else {'config':dict(DEFAULTS),'jobs':[],'message':'No search yet'}

def view(app):
    data=latest(app)
    if data.get('status')=='running' and not STATUS['running']:
        data=dict(data,status='interrupted',message='The previous search was interrupted. Run it again to finish.')
    public=dict(data)
    public['jobs']=[{k:v for k,v in j.items() if k!='scan_text'} for j in data.get('jobs',[])]
    public['activity']=dict(STATUS)
    public['limits']={'description_limit':MAX_DETAILS,'cooldown_seconds':COOLDOWN}
    return public

def store(app,data,run_id=None):
    with app.connect() as db:
        if run_id is None:
            cur=db.execute('INSERT INTO linkedin_searches(payload) VALUES (?)',(json.dumps(data),))
            return cur.lastrowid
        db.execute('UPDATE linkedin_searches SET payload=? WHERE id=?',(json.dumps(data),run_id))
    return run_id

def start(app,body):
    global LAST_REQUEST
    config=validate(body)
    if not LOCK.acquire(blocking=False):return {'running':True,'message':'A LinkedIn search is already running'}
    if time.monotonic()-LAST_REQUEST<COOLDOWN:
        LOCK.release();raise ValueError('Wait one minute between LinkedIn searches. You can re-match saved results immediately.')
    LAST_REQUEST=time.monotonic()
    try:
        previous=latest(app)
        pending={'config':config,'jobs':previous.get('jobs',[]),'status':'running','started_at':now(),
                 'message':'Fetching public search pages. Previous results stay visible until this finishes.',
                 'results_config':previous.get('results_config',previous.get('config')), 'checked_at':previous.get('checked_at')}
        run_id=store(app,pending);STATUS.update(running=True,message='Fetching public search results…',completed=0)
        threading.Thread(target=run,args=(app,config,run_id,pending),daemon=True).start()
    except Exception:
        STATUS.update(running=False);LOCK.release();raise
    return {'running':True}

def run(app,config,run_id,previous):
    try:
        jobs,warnings,pagination,page_failed=collect_pages(config)
        checked=0;deadline=time.monotonic()+100
        ordered=sorted(jobs,key=lambda j:(bool(match(j,config)['excluded']),-match(j,config)['keyword_count']))
        for j in ([] if page_failed else ordered[:MAX_DETAILS]):
            if time.monotonic()>deadline:
                warnings.append('Description time budget reached; remaining jobs are card-only.');break
            try:
                detail=fetch_page(j['url']);j['scan_text']=parse_description(detail)
                j['detail_status']='Scanned' if j['scan_text'] else 'Description not publicly readable'
                checked+=bool(j['scan_text'])
            except Blocked as e:
                j['detail_status']='Blocked';warnings.append(str(e));break
            except (RuntimeError,ValueError) as e:
                j['detail_status']='Unavailable';warnings.append(str(e))
            STATUS.update(completed=checked,message=f'Read {checked} descriptions; at most {MAX_DETAILS} per search.')
            time.sleep(1)
        results=[match(j,config) for j in jobs]
        results.sort(key=lambda j:({'match':0,'unknown':1,'no_match':2,'excluded':3}[j['match_status']],-j['keyword_count']))
        data={'config':config,'results_config':config,'jobs':results,'status':'partial' if page_failed else 'complete','checked_at':now(),'search_url':search_url(config),
              'pagination':pagination,
              'description_count':checked,'message':f'Fetched {len(jobs)} unique jobs across {pagination["pages_fetched"]} pages; scanned {checked} descriptions. '+('Search interrupted; earlier pages retained.' if page_failed else 'Public results may be incomplete.'),
              'warnings':list(dict.fromkeys(warnings))}
        store(app,data,run_id);STATUS.update(message=data['message'])
    except Exception as e:
        message=str(e) if isinstance(e,(Blocked,RuntimeError,ValueError)) else 'Search could not finish. Previous results retained.'
        store(app,dict(previous,status='error',message=message),run_id);STATUS.update(message=message)
    finally:
        STATUS.update(running=False);LOCK.release()

def TreeText(page):
    tree=Tree();tree.feed(page);return tree.root.text()

def rematch(app,body):
    config=validate(body)
    if not LOCK.acquire(blocking=False):raise ValueError('Wait for the running search before re-matching')
    try:
        data=latest(app)
        # Local matching cannot pretend to change the remote query, date or location.
        basis=data.get('results_config') or data.get('config') or {}
        for key in ['query','location','posted','remote','limit']:
            if config[key]!=basis.get(key):raise ValueError('Query/location/date changes require a new LinkedIn search')
        if config['pages']!=basis.get('pages',1):raise ValueError('Page-limit changes require a new LinkedIn search')
        data['config']=config;data['results_config']=config
        data['jobs']=[match(j,config) for j in data.get('jobs',[])]
        data['jobs'].sort(key=lambda j:({'match':0,'unknown':1,'no_match':2,'excluded':3}[j['match_status']],-j['keyword_count']))
        data.update(message='Keyword rules re-applied to saved text. No network request; snapshot date unchanged.')
        store(app,data)
    finally:LOCK.release()
    return {'saved':True}

def track(app,ident):
    if not isinstance(ident,str) or not ident.isdigit():raise ValueError('Invalid LinkedIn job ID')
    data=latest(app);job=next((j for j in data.get('jobs',[]) if j['id']==ident),None)
    if not job:raise ValueError('Job is not in the current saved search')
    jid='linkedin:'+ident
    with app.connect() as db:
        for row in db.execute('SELECT id,payload FROM jobs'):
            existing=json.loads(row['payload'])
            if row['id']==jid or any(job_id(existing.get(k,''))==ident for k in ['source_url','apply_url','discovery_url']):
                return {'id':row['id'],'existing':True}
        reg,country,rank=app.region_of(job.get('location',''))
        item=dict(id=jid,source_id='linkedin:public',company=job.get('company','Unknown'),title=job['title'],location=job.get('location',''),
            country=country,region=reg,location_rank=rank,apply_url=job['url'],source_url=job['url'],discovery_url=job['url'],
            discovered_via=['LinkedIn public search'],status_source='linkedin_snapshot',reviewed=False,fit_band='Needs review',
            fit_reasons='Keyword overlap in a LinkedIn snapshot: '+(', '.join(job.get('matched',[])) or 'no configured terms found')+'. Not a resume-fit assessment.',
            requirements='Review the original listing for complete requirements.',description='Description coverage: '+job.get('coverage','Card only'),
            full_description=job.get('scan_text',''),jd_checked_at=data.get('checked_at'),jd_source_url=job['url'],
            gaps='Verify role requirements, location/work eligibility and current availability with the employer.',
            role_track='LinkedIn discovery',salary_text='Not verified',visa_text='Unknown — check with employer',
            verified_at=None,discovered_at=data.get('checked_at'),verification_method='LinkedIn public snapshot; not employer-verified')
        db.execute('INSERT INTO jobs VALUES (?,?,?)',(jid,'linkedin:public',json.dumps(item)))
    return {'id':jid,'existing':False}
