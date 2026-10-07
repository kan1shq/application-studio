"""Local, extractive application drafting. Source statements are never rewritten."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Separate skills deliberately: Java is not JavaScript, SQL is not PostgreSQL,
# and Azure experience does not imply AWS experience.
SKILLS = {
    'Python': r'\bpython\b', 'Java': r'\bjava\b', 'JavaScript': r'\bjavascript\b',
    'TypeScript': r'\btypescript\b', 'Go': r'\bgolang\b|\bGo\b',
    'Rust': r'\brust\b', 'C++': r'(?<!\w)c\+\+', 'SQL': r'\bsql\b',
    'PostgreSQL': r'\bpostgres(?:ql)?\b', 'MySQL': r'\bmysql\b',
    'Redis': r'\bredis\b', 'MongoDB': r'\bmongodb\b',
    'Kafka': r'\bkafka\b', 'Kubernetes': r'\bkubernetes\b|\bk8s\b|\baks\b',
    'Docker': r'\bdocker\b', 'Azure': r'\bazure\b|\baks\b',
    'AWS': r'\baws\b|amazon web services', 'GCP': r'\bgcp\b|google cloud',
    'Spring Boot': r'\bspring\s*boot\b', 'React': r'\breact\b',
    'Django': r'\bdjango\b', 'FastAPI': r'\bfastapi\b',
    'Airflow': r'\bairflow\b', 'Spark': r'\b(?:py)?spark\b',
    'Databricks': r'\bdatabricks\b', 'Terraform': r'\bterraform\b',
    'CI/CD': r'\bci/cd\b|github actions|continuous integration',
    'Testing': r'\btest(?:s|ing)?\b|playwright|pytest',
    'Microservices': r'\bmicroservices?\b',
    'Distributed systems': r'distributed systems',
    'APIs': r'\bapis?\b|\brestful\b|\bgraphql\b',
    'Observability': r'\bobservability\b|\bmonitoring\b|\btracing\b',
    'LLM': r'\bllms?\b|large language models?',
    'RAG': r'\brag\b|retrieval.augmented', 'MCP': r'\bmcp\b',
    'LangChain': r'\blangchain\b', 'LangGraph': r'\blanggraph\b',
    'PyTorch': r'\bpytorch\b', 'TensorFlow': r'\btensorflow\b|\bkeras\b',
    'Machine learning': r'machine learning|\bml\b',
    'Evaluation': r'\bevals?\b|\bevaluation\b|\bbenchmark(?:s|ing)?\b',
}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_profile(value):
    if not isinstance(value, dict):
        raise ValueError('Profile must be a JSON object')
    def string(s, limit=12000):
        if not isinstance(s, str) or len(s) > limit or '\x00' in s:
            raise ValueError('Invalid profile text')
        return s.strip()
    name = string(value.get('name', ''), 200)
    if not name:
        raise ValueError('A name is required')
    contacts = value.get('contacts', [])
    sections = value.get('sections', [])
    if not isinstance(contacts, list) or len(contacts) > 10:
        raise ValueError('Contacts must be a list of at most 10 strings')
    if not isinstance(sections, list) or not 1 <= len(sections) <= 20:
        raise ValueError('Supply 1-20 structured resume sections')
    clean = {'version': 1, 'name': name, 'contacts': [string(s, 250) for s in contacts],
             'source_label': string(value.get('source_label', 'User supplied'), 250),
             'full_details': string(value.get('full_details', ''), 80000), 'sections': []}
    links=value.get('contact_links',{})
    if not isinstance(links,dict) or len(links)>10:raise ValueError('Invalid contact links')
    clean['contact_links']={}
    for label,url in links.items():
        label=string(label,250);url=string(url,1000)
        if label not in clean['contacts'] or not re.match(r'^(https?://|mailto:)',url):raise ValueError('Contact links must use http, https or mailto and a listed label')
        clean['contact_links'][label]=url
    for sec in sections:
        if not isinstance(sec, dict) or sec.get('kind') not in ('education', 'experience', 'projects', 'skills', 'other'):
            raise ValueError('Each section needs a valid kind')
        entries = sec.get('entries', [])
        if not isinstance(entries, list) or not 1 <= len(entries) <= 60:
            raise ValueError('Each section needs 1-60 entries')
        section = {'title': string(sec.get('title', ''), 150), 'kind': sec['kind'], 'entries': []}
        if not section['title']:
            raise ValueError('Section title is required')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Entry must be an object')
            item = {k: string(entry.get(k, ''), 1500) for k in ('title', 'subtitle', 'dates', 'location')}
            bullets = entry.get('bullets', [])
            if not isinstance(bullets, list) or len(bullets) > 60:
                raise ValueError('Bullets must be a list of at most 60 statements')
            item['bullets'] = [string(s) for s in bullets if isinstance(s, str) and s.strip()]
            if len(item['bullets']) != len(bullets):
                raise ValueError('Every bullet must be a nonempty string')
            if not item['title']:
                raise ValueError('Entry title is required')
            groups=entry.get('groups',[])
            if not isinstance(groups,list) or len(groups)>30:
                raise ValueError('Groups must be a list of at most 30 subheadings')
            item['groups']=[]
            emphasis=entry.get('emphasis',[])
            if not isinstance(emphasis,list) or len(emphasis)>100:raise ValueError('Emphasis must be a list')
            item['emphasis']=[string(s,500) for s in emphasis if s]
            for group in groups:
                if not isinstance(group,dict) or not isinstance(group.get('bullets'),list) or not 1<=len(group['bullets'])<=60:
                    raise ValueError('Each subheading needs 1-60 bullets')
                heading=string(group.get('heading',''),300)
                if not heading: raise ValueError('Subheading is required')
                statements=[string(b) for b in group['bullets']]
                if not all(statements): raise ValueError('Empty subheading bullet')
                item['groups'].append({'heading':heading,'bullets':statements})
            section['entries'].append(item)
        clean['sections'].append(section)
    return clean


def load_profile(data):
    path = Path(data) / 'resume_profile.json'
    return validate_profile(json.loads(path.read_text(encoding='utf-8'))) if path.exists() else None


def save_profile(data, value):
    profile = validate_profile(value)
    path = Path(data) / 'resume_profile.json'
    if path.exists():
        backup = Path(data) / 'backups'
        backup.mkdir(exist_ok=True)
        old = path.read_bytes()
        (backup / ('resume-' + hashlib.sha256(old).hexdigest()[:16] + '.json')).write_bytes(old)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    return profile


def topics(text):
    found = set()
    for name, pattern in SKILLS.items():
        # Go's ordinary English verb is not evidence of the programming language.
        flags = 0 if name == 'Go' else re.I
        if re.search(pattern, text, flags):
            found.add(name)
    return found


def evidence(profile):
    result = []
    for si, sec in enumerate(profile['sections']):
        for ei, entry in enumerate(sec['entries']):
            context = ' | '.join(filter(None, [entry['title'], entry['subtitle'], entry['dates']]))
            result.append({'id': f'{si}.{ei}.heading', 'text': context, 'kind': 'listed', 'context': context})
            for bi, text in enumerate(entry['bullets']):
                kind = 'listed' if sec['kind'] == 'skills' else 'example'
                result.append({'id': f'{si}.{ei}.{bi}', 'text': text, 'kind': kind, 'context': context})
            for gi,group in enumerate(entry.get('groups',[])):
                result.append({'id':f'{si}.{ei}.group.{gi}.heading','text':group['heading'],'kind':'listed','context':context})
                for bi,text in enumerate(group['bullets']):
                    result.append({'id':f'{si}.{ei}.group.{gi}.{bi}','text':text,'kind':'listed' if sec['kind']=='skills' else 'example','context':context+' | '+group['heading']})
    for i, line in enumerate(profile.get('full_details', '').splitlines()):
        if line.strip():
            result.append({'id': f'detail.{i}', 'text': line.strip(), 'kind': 'unstructured', 'context': 'Full detail source; review context'})
    return result


def job_text(job):
    if job.get('full_description', '').strip():
        return job['full_description'].strip(), 'full_jd'
    return '\n'.join(str(job.get(k, '') or '') for k in ('requirements', 'preferred', 'key_evidence_excerpt')).strip(), 'summary_only'


def analyze(profile, job):
    text, coverage = job_text(job)
    required = topics(text)
    statements = evidence(profile)
    matches = []
    for skill in sorted(required):
        refs = [e for e in statements if skill in topics(e['text'])]
        concrete = [e for e in refs if e['kind'] == 'example']
        matches.append({'skill': skill, 'status': 'example_in_resume' if concrete else 'listed_only' if refs else 'not_evidenced',
                        'evidence': (concrete or refs)[:4],
                        'jd_excerpt': next((s.strip()[:900] for s in text.splitlines() if skill in topics(s)), text[:900])})
    covered = sum(m['status'] != 'not_evidenced' for m in matches)
    return {'job_id': job.get('id', 'custom'), 'company': job.get('company', ''), 'title': job.get('title', ''),
            'fit_band': job.get('fit_band', 'Needs review'), 'coverage': coverage, 'source_url': job.get('source_url', ''),
            'jd_checked_at': job.get('jd_checked_at') or job.get('verified_at'), 'status_source': job.get('status_source'),
            'profile_hash': fingerprint(profile), 'jd_hash': fingerprint(text), 'topics': matches,
            'overlap_percent': round(100 * covered / len(matches)) if matches else None,
            'missing': [m['skill'] for m in matches if m['status'] == 'not_evidenced'],
            'listed_only': [m['skill'] for m in matches if m['status'] == 'listed_only'],
            'review_requirements': [s.strip() for s in text.splitlines() if re.search(r'\byears?\b|\bvisa\b|sponsor|authorization|degree|fluent|citizenship|clearance', s, re.I)][:25],
            'note': 'Heuristic topic evidence, not ATS score or qualification verdict. JD mentions may be optional, alternatives, or negated. Missing evidence is not proof of missing ability. Review the full JD, seniority, language, location, and work authorization.'}


def gap_report(profile, jobs):
    rows = []
    excluded = Counter()
    for job in jobs:
        if job.get('status_source') in ('not_listed', 'closed') or job.get('application_status') in ('Rejected', 'Passed'):
            excluded['closed_or_passed'] += 1
            continue
        row = analyze(profile, job)
        existing = job.get('fit_band') in ('strong', 'possible', 'high')
        provisional = row['coverage'] == 'full_jd' and len(row['topics']) >= 3 and (row['overlap_percent'] or 0) >= 60
        if existing or provisional:
            row['selection'] = 'previously reviewed strong/possible' if existing else 'provisional topic overlap >=60%; needs human review'
            rows.append(row)
        else:
            excluded['below_threshold_or_insufficient_jd'] += 1
    rows.sort(key=lambda r: (r['coverage'] != 'full_jd', -(r['overlap_percent'] or 0), r['company']))
    counts = Counter(s for row in rows for s in row['missing'])
    return {'generated_at': stamp(), 'profile_hash': fingerprint(profile), 'profile_source': profile['source_label'],
            'jobs_scanned': len(jobs), 'prospects': len(rows), 'full_jd_count': sum(r['coverage'] == 'full_jd' for r in rows),
            'excluded': dict(excluded), 'priority_gaps': [{'skill': s, 'jobs': n} for s, n in counts.most_common()],
            'jobs': rows, 'method': 'All saved non-closed/non-passed strong or possible roles, plus full-JD candidates with >=3 detected topics and >=60% source mention overlap. Summary-only assessments are incomplete. Keyword overlap does not replace a requirements review.'}


def tex(value):
    mapping = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
               '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    value = str(value).replace('\u2013', '--').replace('\u2014', '---').replace('\u2019', "'").replace('\u2018', "'")
    return ''.join(mapping.get(c, c) for c in value)


PREAMBLE = r'''% Resume template adapted from Jake Gutierrez, based on sb2nov/resume.
% MIT license. See THIRD_PARTY_NOTICES.md in the source distribution.
\documentclass[letterpaper,11pt]{article}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage[usenames,dvipsnames]{color}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\ifdefined\pdfgentounicode
  \input{glyphtounicode}
  \pdfgentounicode=1
\fi
\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}
\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\parindent}{0pt}
\setlength{\tabcolsep}{0in}
\titleformat{\section}{\vspace{-4pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule\vspace{-5pt}]
\newcommand{\resumeItem}[1]{\item\small{{#1\vspace{-2pt}}}}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
  \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} & #2 \\
    \textit{\small#3} & \textit{\small#4} \\
  \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[2]{
  \item\begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
    \small#1 & #2 \\
  \end{tabular*}\vspace{-7pt}
}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in,label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
\begin{document}
'''


def header(profile):
    contacts=[]
    for label in profile['contacts']:
        url=profile.get('contact_links',{}).get(label)
        contacts.append(r'\href{'+tex(url)+r'}{\underline{'+tex(label)+'}}' if url else tex(label))
    return '\\begin{center}\n'+r'\textbf{\Huge\scshape '+tex(profile['name'])+r'} \\ \vspace{1pt}'+'\n\\small '+r' $|$ '.join(contacts)+'\n\\end{center}\n'


def emphasized(text, phrases):
    phrases=sorted({p for p in phrases if p and p in text},key=len,reverse=True)
    if not phrases:return tex(text)
    pattern='('+ '|'.join(re.escape(p) for p in phrases)+')'
    return ''.join(r'\textbf{'+tex(s)+'}' if s in phrases else tex(s) for s in re.split(pattern,text))


def generate(profile, job, max_bullets=4):
    if type(max_bullets) is not int or not 1 <= max_bullets <= 12:
        raise ValueError('Bullet limit must be 1-12')
    jd, coverage = job_text(job)
    if coverage != 'full_jd' or len(jd) < 80:
        raise ValueError('A full JD (at least 80 characters) is required. Paste it or refresh the official source first.')
    wanted = topics(jd)
    def rank(text):
        return len(topics(text) & wanted)
    parts = [PREAMBLE, header(profile)]
    plain = [profile['name'], ' | '.join(profile['contacts'])]
    selected = []
    for si, section in enumerate(profile['sections']):
        parts.append(r'\section{' + tex(section['title']) + '}\n')
        parts.append('\\resumeSubHeadingListStart\n')
        plain.append(section['title'])
        entries = list(enumerate(section['entries']))
        if section['kind'] == 'projects':
            entries.sort(key=lambda pair: -rank(' '.join([pair[1]['title']] + pair[1]['bullets']+[b for g in pair[1].get('groups',[]) for b in g['bullets']])))
        for ei, entry in entries:
            title,separator,technologies=entry['title'].partition(' | ')
            title_tex=r'\textbf{'+tex(title)+'}'+(r' $|$ '+r'\emph{\small{'+tex(technologies)+'}}' if separator else '')
            first_right=entry['location'] if section['kind']=='education' else entry['dates']
            second_right=entry['dates'] if section['kind']=='education' else entry['location']
            if section['kind']=='skills':
                parts.append(r'\item\small{'+title_tex+': '+tex(entry['subtitle'])+'}\\vspace{-5pt}\n')
            elif section['kind']=='projects' and not entry['subtitle'] and not entry['location']:
                parts.append(r'\resumeProjectHeading{'+title_tex+'}{'+tex(entry['dates'])+'}\n')
            else:
                parts.append(r'\resumeSubheading{'+title_tex+'}{'+tex(first_right)+'}{'+tex(entry['subtitle'])+'}{'+tex(second_right)+'}\n')
            plain.append(' | '.join(filter(None, [entry['title'], entry['dates'], entry['subtitle'], entry['location']])))
            bullets = list(enumerate(entry['bullets']))
            if section['kind'] not in ('skills', 'education'):
                bullets.sort(key=lambda pair: -rank(pair[1]))
                bullets = bullets[:max_bullets]
            if bullets:
                parts.append('\\resumeItemListStart\n')
                for bi, statement in bullets:
                    parts.append('\\resumeItem{' + emphasized(statement,entry.get('emphasis',[])) + '}\n')
                    plain.append('- ' + statement)
                    selected.append({'id': f'{si}.{ei}.{bi}', 'text': statement, 'context': ' | '.join(filter(None,[entry['title'],entry['subtitle']])), 'kind':section['kind'], 'overlap': rank(statement)})
                parts.append('\\resumeItemListEnd\n')
            for gi,group in enumerate(entry.get('groups',[])):
                parts.append(r'\vspace{5pt}\par\textit{\small '+tex(group['heading'])+'}\\par\n\\resumeItemListStart\n')
                plain.append(group['heading'])
                ranked=sorted(enumerate(group['bullets']),key=lambda pair:-rank(pair[1]))[:max_bullets]
                for bi,statement in ranked:
                    parts.append('\\resumeItem{'+emphasized(statement,entry.get('emphasis',[]))+'}\n')
                    plain.append('- '+statement)
                    selected.append({'id':f'{si}.{ei}.group.{gi}.{bi}','text':statement,'context':' | '.join(filter(None,[entry['title'],entry['subtitle'],group['heading']])),'kind':section['kind'],'overlap':rank(statement)})
                parts.append('\\resumeItemListEnd\n')
        parts.append('\\resumeSubHeadingListEnd\n')
    parts.append('\\end{document}\n')
    # Cover letter cites exact statements and names their source context. No invented
    # motivation, company knowledge, titles, skills, durations, or achievements.
    strongest = sorted([s for s in selected if s['overlap'] and s['kind'] in ('experience','projects','other')], key=lambda s: -s['overlap'])[:3]
    company, role = job.get('company', '').strip(), job.get('title', '').strip()
    opening = f'I am applying for the {role or "advertised"} position' + (f' at {company}' if company else '') + '.'
    letter = ['Dear Hiring Team,', opening, 'The following examples from my experience relate to topics in your job description:']
    letter += [f'{s["context"]}: {s["text"]}' for s in strongest]
    if not strongest:
        letter.append('I would welcome a discussion about how my background relates to this role.')
    letter += ['Thank you for considering my application. I would welcome the opportunity to discuss these examples and the requirements of the role.', 'Sincerely,\n' + profile['name']]
    cover = PREAMBLE + header(profile) + '\\vspace{20pt}\n' + '\n\\par\\vspace{10pt}\n'.join(tex(p).replace('\n', '\\par\n') for p in letter) + '\n\\end{document}\n'
    return {'resume_tex': ''.join(parts), 'resume_text': '\n'.join(plain), 'cover_letter_tex': cover,
            'cover_letter_text': '\n\n'.join(letter), 'analysis': analyze(profile, job),
            'audit': {'created_at': stamp(), 'profile_hash': fingerprint(profile), 'jd_hash': fingerprint(jd),
                      'selected_statements': selected, 'cover_letter_statement_ids': [s['id'] for s in strongest],
                      'method': 'Deterministic selection and reordering; source bullets, metrics, estimates and dates retained verbatim. Full details inform gap analysis; only structured entries are printed. Review before sending.'}}
