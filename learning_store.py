"""Local learning history and reference-only curriculum updates."""
import hashlib
import ipaddress
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler

SOURCE_HOSTS={'www.fanout.sh','fanout.sh'}
SOURCE_PATHS={'/','/system/overview','/ai/overview','/ml-math/overview','/inference-eng','/updates','/papers','/daily','/blog','/labs','/tools','/resources','/roadmap','/roadmaps','/ai-engineering','/open-robotics','/robot-arm','/rl','/llm-training','/diffusion','/finetuning','/math-decoder','/knowledge-graph','/study-with-me'}

class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed=urlparse(newurl)
        if parsed.scheme!='https' or parsed.hostname not in SOURCE_HOSTS:
            raise ValueError('Redirect outside source')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def open_public(request, timeout):
    return build_opener(PublicRedirects()).open(request,timeout=timeout)

class Conflict(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS learning_state(item_id TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS learning_attempts(id INTEGER PRIMARY KEY,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS learning_sessions(day INTEGER PRIMARY KEY,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS curriculum_snapshots(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS curriculum_adoptions(item_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
    ''')

def substantive(state):
    return bool(state.get('tasks') or state.get('notes') or state.get('minimum_done') or state.get('energy','standard') != 'standard')

def capture(db, day, state, plan):
    definition = next((d for d in plan.get('days',[]) if d['day']==day),None)
    if definition and substantive(state):
        db.execute('INSERT OR IGNORE INTO learning_sessions VALUES (?,?)',(day,json.dumps({'definition':definition,'captured_at':now()})))

def migrate_sessions(app, old_plan):
    with app.connect() as db:
        initialize(db)
        for row in db.execute('SELECT day,payload FROM prep_state').fetchall():
            capture(db,row['day'],json.loads(row['payload']),old_plan)

def view(db,catalog=None):
    states={r['item_id']:json.loads(r['payload']) for r in db.execute('SELECT * FROM learning_state')}
    attempts=[dict(json.loads(r['payload']),attempt_id=r['id']) for r in db.execute('SELECT * FROM learning_attempts ORDER BY id')]
    kinds={i['id']:i.get('kind') for i in (catalog or {}).get('items',[])}
    latest={}
    for a in attempts:
        if kinds.get(a['id'],a.get('kind'))=='dsa': latest[a['id']]=a
    retries=[{'item_id':a['id'],'attempt_id':a['attempt_id'],'due_day':a['day']+offset,'backlog':a['day']+offset>140} for a in latest.values() for offset in (2,7,14)]
    return {'states':states,'attempts':attempts,'retries':retries,'sessions':{str(r['day']):json.loads(r['payload']) for r in db.execute('SELECT * FROM learning_sessions')},'snapshots':[json.loads(r['payload']) for r in db.execute('SELECT * FROM curriculum_snapshots ORDER BY rowid')],'adoptions':[json.loads(r['payload']) for r in db.execute('SELECT * FROM curriculum_adoptions')]}

def text(value, name, limit=12000):
    if not isinstance(value,str) or len(value)>limit: raise ValueError('Invalid '+name)
    return value

def known(db,catalog,item_id):
    text(item_id,'id',300)
    if not any(x['id']==item_id for x in catalog.get('items',[])) and not db.execute('SELECT 1 FROM curriculum_adoptions WHERE item_id=?',(item_id,)).fetchone(): raise ValueError('Unknown learning item')

def save_state(db,catalog,body):
    known(db,catalog,body.get('id'))
    if body.get('status') not in {'not_started','studied','practised','demonstrated'}: raise ValueError('Invalid status')
    db.execute('BEGIN IMMEDIATE')
    row=db.execute('SELECT payload FROM learning_state WHERE item_id=?',(body['id'],)).fetchone()
    version=json.loads(row['payload']).get('version',0) if row else 0
    if type(body.get('version',0)) is not int or body.get('version',0)!=version: raise Conflict('Learning state changed; reload before saving')
    state={k:text(body.get(k,''),k) for k in ('notes','evidence')}
    state.update(id=body['id'],status=body['status'],version=version+1,updated_at=now())
    db.execute('INSERT OR REPLACE INTO learning_state VALUES (?,?,?)',(body['id'],json.dumps(state),state['updated_at']))
    return {'saved':True,'state':state}

def attempt(db,catalog,body):
    known(db,catalog,body.get('id'))
    if body.get('outcome') not in {'unsolved','assisted','independent'}: raise ValueError('Invalid outcome')
    for key,low,high in [('day',1,140),('minutes',0,1440),('hints',0,100)]:
        if type(body.get(key)) is not int or not low<=body[key]<=high: raise ValueError('Invalid '+key)
    result={k:body[k] for k in ('id','day','outcome','minutes','hints')}
    if body['outcome']=='independent' and body['hints']>0: raise ValueError('Independent attempts cannot include hints')
    item=next((i for i in catalog.get('items',[]) if i['id']==body['id']),{})
    result['kind']=item.get('kind','reference')
    result.update({k:text(body.get(k,''),k) for k in ('notes','evidence')})
    if 'score' in body:
        if type(body['score']) not in (int,float) or not 0<=body['score']<=20: raise ValueError('Invalid score; rubric range is 0 to 20')
        result['score']=body['score']
    if 'client_nonce' in body:
        nonce=text(body['client_nonce'],'client_nonce',200)
        if not nonce: raise ValueError('Invalid client_nonce')
        result['client_nonce']=nonce
    db.execute('BEGIN IMMEDIATE')
    if result.get('client_nonce'):
        for row in db.execute('SELECT id,payload FROM learning_attempts'):
            previous=json.loads(row['payload'])
            if previous.get('client_nonce')==result['client_nonce'] and previous['id']==result['id']:
                if any(previous.get(k)!=v for k,v in result.items()): raise ValueError('Client nonce already used for a different attempt')
                return dict(previous,attempt_id=row['id'])
    result['created_at']=now()
    cursor=db.execute('INSERT INTO learning_attempts(payload) VALUES (?)',(json.dumps(result),))
    return dict(result,attempt_id=cursor.lastrowid)

def source_url(value):
    if not isinstance(value,str): raise ValueError('Invalid source URL')
    parsed=urlparse(value)
    if parsed.scheme!='https' or parsed.hostname not in SOURCE_HOSTS or parsed.username or parsed.password or parsed.query or parsed.fragment or not (parsed.path.rstrip('/') in SOURCE_PATHS or parsed.path=='/' or parsed.path.startswith(('/roadmaps/','/ai/','/system/','/ml-math/','/inference-eng/','/courses/'))): raise ValueError('Source must be an allowed public Fanout page')
    return value

def import_snapshot(db,body):
    source=source_url(body.get('source_url'))
    observed=text(body.get('observed_at'),'observed_at',100)
    try: datetime.fromisoformat(observed.replace('Z','+00:00'))
    except ValueError: raise ValueError('Invalid observed_at')
    if type(body.get('complete')) is not bool or not isinstance(body.get('items'),list) or len(body['items'])>500: raise ValueError('Invalid import')
    items=[]; seen=set()
    for raw in body['items']:
        if not isinstance(raw,dict): raise ValueError('Invalid source item')
        url=text(raw.get('url'),'url',2000); parsed=urlparse(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.hostname.lower() in {'localhost','127.0.0.1','::1'} or parsed.username or parsed.password: raise ValueError('Invalid public item URL')
        try: address=ipaddress.ip_address(parsed.hostname)
        except ValueError: address=None
        if address and not address.is_global: raise ValueError('Private item URL is not a public reference')
        source_key=text(raw['source_key'],'source_key',300) if 'source_key' in raw else None
        identity=(url,source_key)
        if identity in seen: raise ValueError('Duplicate URL/source_key')
        seen.add(identity)
        hash_input=url if source_key is None else url+'#'+source_key
        items.append({'id':'fanout:'+hashlib.sha256(hash_input.encode()).hexdigest()[:20],'url':url,'title':text(raw.get('title'),'title',500),'access':text(raw.get('access'),'access',100),'summary':text(raw.get('summary',''),'summary',12000),'kind':text(raw.get('kind','reference'),'kind',100)})
        if source_key is not None: items[-1]['source_key']=source_key
        for key in ('module','code'):
            if key in raw: items[-1][key]=text(raw[key],key,500)
    prior=db.execute('SELECT payload FROM curriculum_snapshots ORDER BY rowid DESC').fetchall()
    candidates=[json.loads(r['payload']) for r in prior if json.loads(r['payload'])['source_url']==source]
    previous=next((s for s in candidates if s.get('complete')),candidates[0] if candidates else {})
    old={i['id']:i for i in previous.get('items',[])}; current={i['id']:i for i in items}
    snapshot={'source_url':source,'observed_at':observed,'complete':body['complete'],'items':items,'diff':{'additions':[i for k,i in current.items() if k not in old],'changes':[i for k,i in current.items() if k in old and i!=old[k]],'removals':[i for k,i in old.items() if k not in current] if body['complete'] else []}}
    snapshot['id']=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()[:24]
    db.execute('INSERT OR IGNORE INTO curriculum_snapshots VALUES (?,?)',(snapshot['id'],json.dumps(snapshot)))
    return snapshot

def adopt(db,body):
    row=db.execute('SELECT payload FROM curriculum_snapshots WHERE id=?',(body.get('snapshot_id'),)).fetchone()
    item=next((i for i in json.loads(row['payload'])['items'] if i['id']==body.get('item_id')),None) if row else None
    if not item: raise ValueError('Unknown snapshot item')
    previous=db.execute('SELECT payload FROM curriculum_adoptions WHERE item_id=?',(item['id'],)).fetchone()
    if previous:
        previous=json.loads(previous['payload'])
        if previous.get('snapshot_id')==body['snapshot_id']:
            return {'saved':True,'item':previous}
    item=dict(item,kind='reference',snapshot_id=body['snapshot_id'],adopted_at=now())
    db.execute('INSERT INTO curriculum_adoptions VALUES (?,?) ON CONFLICT(item_id) DO UPDATE SET payload=excluded.payload',(item['id'],json.dumps(item)))
    return {'saved':True,'item':item}

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.items=[]; self.href=None; self.label=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.href=dict(attrs).get('href'); self.label=[]
    def handle_data(self,data):
        if self.href: self.label.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            self.items.append((self.href,' '.join(self.label).strip())); self.href=None

def refresh(db,body):
    source=source_url(body.get('source_url'))
    try:
        with open_public(Request(source,headers={'User-Agent':'ApplicationStudio/1.0'}),timeout=15) as response:
            if urlparse(response.geturl()).hostname not in SOURCE_HOSTS: raise ValueError('Redirect outside source')
            markup=response.read(2000001)
            if len(markup)>2000000: raise ValueError('Source too large')
        parser=Links(); parser.feed(markup.decode('utf-8','replace')); items={}
        for href,title in parser.items:
            url=urljoin(source,href); parsed=urlparse(url)
            if title and parsed.hostname in SOURCE_HOSTS and parsed.scheme=='https' and parsed.path not in ('','/'):
                items[url]={'url':url,'title':title,'access':'public','kind':'reference'}
        if not items: raise ValueError('No readable article links; previous snapshots retained')
        return import_snapshot(db,{'source_url':source,'observed_at':now(),'items':list(items.values()),'complete':False})
    except Exception as exc:
        return {'error':str(exc),'retained':True}
