"""Refresh full JDs for existing jobs only, preserving application and learning state."""
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
import resume_studio


def main():
    server.initialize()
    backup=server.DATA/'backups'
    backup.mkdir(exist_ok=True)
    with server.connect() as db, sqlite3.connect(backup/('before-resume-evidence-'+server.now().replace(':','-')+'.sqlite')) as dest:
        db.backup(dest)
    jobs=server.snapshot()['jobs']
    sources=[s for s in server.read_json('sources.json',[]) if s.get('enabled',True) and any(j.get('source_id')==s['id'] for j in jobs)]
    results=[]
    def fetch(source):
        try:
            feed,url=server.fetch_board(source)
            return source,feed,url,None
        except Exception as exc:return source,[],None,str(exc)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(fetch,s) for s in sources]):
            source,feed,url,error=future.result()
            count=0
            if not error:
                by_id={str(j['external_id']):j for j in feed}
                with server.connect() as db:
                    for row in db.execute('SELECT id,payload FROM jobs WHERE source_id=?',(source['id'],)).fetchall():
                        job=json.loads(row['payload']);raw=by_id.get(str(job.get('external_id')))
                        if raw:
                            job.update(full_description=raw['description'],jd_checked_at=server.now(),jd_source_url=url,jd_origin='public ATS feed')
                            db.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(job),row['id']));count+=1
            results.append({'source':source['id'],'hydrated':count,'error':error})
            print(json.dumps(results[-1]),flush=True)
    # Recover already-scanned LinkedIn descriptions without another network request.
    with server.connect() as db:
        for row in db.execute('SELECT payload FROM linkedin_searches ORDER BY id DESC').fetchall():
            search=json.loads(row['payload'])
            for item in search.get('jobs',[]):
                if not item.get('scan_text'):continue
                for saved in db.execute('SELECT id,payload FROM jobs').fetchall():
                    job=json.loads(saved['payload'])
                    if job.get('full_description'):continue
                    if any(server.linkedin_search.job_id(job.get(k,''))==item['id'] for k in ('source_url','apply_url','discovery_url')):
                        job.update(full_description=item['scan_text'],jd_checked_at=search.get('checked_at'),jd_source_url=item.get('url'),jd_origin='saved LinkedIn public scan')
                        db.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(job),saved['id']))
    profile=resume_studio.load_profile(server.DATA)
    if not profile:raise ValueError('Save a resume profile first')
    report=resume_studio.gap_report(profile,server.snapshot()['jobs'])
    out=server.ROOT/'reports';out.mkdir(exist_ok=True)
    (out/'RESUME_GAP_ANALYSIS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (out/'RESUME_JD_REFRESH.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('jobs_scanned','prospects','full_jd_count','priority_gaps')}))


if __name__=='__main__':main()
