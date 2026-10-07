# Application Studio

A local job tracker, evidence-based resume and cover-letter generator, and a 140-day DSA, system design and AI engineering learning workspace. Python 3.10+ runs the app; no AI API key, npm install, or hosted account is required.

## Start

```sh
python server.py
```

Open **http://127.0.0.1:8767**. On Windows, `Start-Dashboard.ps1` and `Stop-Dashboard.ps1` are convenience launchers. Use `python server.py --port 8768` for a different port. Keep it bound to loopback; it is a personal local application, not a multi-user web service.

The public repository includes one fictional job and a fictional resume profile under `examples/`. It includes no real resume, application history, credentials, scraped job corpus, database, or personal learning progress. On first launch, the local SQLite database is created automatically.

## Generate an application

1. Open **Application drafts**. Import `examples/resume-profile.json`, replace the fictional information with your full factual resume details, and **Save full resume profile**. You can also start from the editor's template.
2. Select a saved job. Paste the complete JD and **Save full JD** if the role has only a summary. The demo job is fictional; do not apply to its example URL.
3. Choose the bullet limit and generate. Download the resume and cover letter as `.tex`, the text preview, and the evidence audit.
4. Compile each `.tex` with pdfLaTeX (TeX Live/MiKTeX/Overleaf) or Tectonic. Inspect the PDF before sending:

```sh
pdflatex -no-shell-escape -interaction=nonstopmode -halt-on-error resume.tex
pdflatex -no-shell-escape -interaction=nonstopmode -halt-on-error cover-letter.tex
# Alternatively:
tectonic resume.tex
tectonic cover-letter.tex
```

The template follows a compact single-column serif resume layout with ruled headings and aligned dates. It retains the supplied Jake Gutierrez/sb2nov template commands, 11pt sizing, spacing and two-cell heading alignment tables. The content is real text with Unicode mapping, not images or text boxes. Heading tables require reading-order verification; tested sample PDFs extract in the expected order. This helps text extraction; no layout can guarantee acceptance by every ATS. Long profiles may span multiple pages. The generator does not shrink text to force one page.

### Fidelity and tailoring

Tailoring is **deterministic and extractive**: it ranks source bullets by JD topic overlap and reorders project entries. Work chronology and all entry headings remain intact. It never fabricates skills, experience, metrics, or qualifications and never removes qualifiers such as “estimated” from selected statements. LaTeX special characters in input are escaped. The cover letter uses selected exact achievements with their work/project context and neutral introductory/closing sentences. It is an editable first draft, not an LLM paraphrase.

The evidence audit records source statement IDs, exact selected text, full profile/JD hashes, timestamp and selection method. Each generation uses the saved profile and saved JD. Save edits before generating again.

The structured profile supports `education`, `experience`, `projects`, `skills` and `other` sections; each has `title` and `entries`. Entries have `title`, `subtitle`, `dates`, `location`, `bullets`, and optional nested subheadings:

```json
{
  "title": "Software Engineer | Python",
  "subtitle": "Your employer",
  "dates": "Start - End",
  "location": "City",
  "bullets": ["Your exact achievement and metric."],
  "groups": [{"heading": "Project or responsibility", "bullets": ["Exact supporting statement."]}]
}
```

Add more single-page resume variants into one full profile, retaining the correct employer/project association. `full_details` is optional free text used for gap context; move achievements into structured entries to print them. Statements present only in extra text or skills lists are labeled as listed evidence, not demonstrated mastery. Profile edits preserve hash-named local backups.

## Jobs and gap analysis

- **Sources & refresh** reads configured public Ashby, Greenhouse and Lever boards. Edit `data/sources.json`; the example config is empty. A source object has `id`, `company`, `provider`, `board`, and `enabled`. Example: `{"id":"ashby:your-board","company":"Company","provider":"ashby","board":"actual-board-token","enabled":true}`. Use a real employer's board token. The inherited title/location discovery filter prioritizes engineering roles in EU and selected Asian locations; customize `relevant()` and `region_of()` in `server.py` for other markets and seniorities.
- **LinkedIn search** uses unauthenticated public results and bounded description reads. It does not use browser cookies or log in. Blocks/rate limits stop the search. Track a result to add it to the job radar; unscanned results need a pasted JD.
- Full fetched descriptions are retained locally with source and timestamp. `python tools/refresh_resume_evidence.py` backs up the database and hydrates full JDs for existing jobs without changing application notes/status or importing additional vacancies.
- **Resume & gaps** compares the current profile with all saved jobs. It includes previously reviewed `strong`/`possible` roles plus explicitly provisional candidates with at least three detected topics and 60% mention overlap. Closed, rejected and passed roles are excluded. The cutoff is a review aid, not a claim that a job is a high-quality match.
- Each result distinguishes achievement examples, listed-only skills, missing evidence, and full-JD versus incomplete-summary coverage. It links exact source statements and JD excerpts. Seniority, required versus optional skills, negation, alternatives, language, location, and work authorization still need human review. A missing keyword is not proof of missing ability; percentages are **not ATS scores or hiring probabilities**.

## Learning workspace

Daily prep, Projects, DSA & system design, Materials & practice, and Learning map share learning evidence and practice attempts. The included plan spans 140 undated days, 15 projects, and coding/system/modern-AI learning objectives. It is a customizable starter plan, not a claim about the user's background. Source links and access/coverage caveats are retained. Third-party course material remains subject to its original terms; linked paid content is not bundled as an accessible course.

The canonical catalog is `data/curriculum.json`; regenerate derived files with:

```sh
python tools/build_curriculum.py
python tools/build_curriculum.py --check
```

## Local data and privacy

Runtime data stays under `data/`, including `workspace.sqlite`, `resume_profile.json`, and backups. Do not commit these files, exported backups, pasted JDs, generated applications, logs, or personal research reports. `.gitignore` excludes them. Git ignore rules do not remove files already committed; inspect staged files before publishing any fork.

The server sends network requests only when job/curriculum refresh or search is requested; resume tailoring and gap analysis run locally. Downloading LaTeX dependencies may contact package servers. Export backup contains private job/learning state; export your resume profile separately and keep both private.

## Verification

```sh
python -m unittest discover -s tests -v
node tests/check_frontend.cjs
python tools/build_curriculum.py --check
```

Node is needed only for frontend contract tests. Tests use temporary databases and fictional fixtures. They cover metric/qualifier preservation, source association, LaTeX escaping, missing-JD rejection, profile edits, gap filters, HTTP routes, job persistence, and learning workflows. Visual PDF inspection remains a separate release check.

Template attribution and MIT notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Optional `contact_links` maps displayed contact labels to HTTP(S)/mailto URLs, and each entry can provide an `emphasis` list of exact source phrases to bold without changing wording.


## Direct PDF downloads

After generating drafts, click **Download resume PDF** or **Download cover letter PDF**. The server compiles the saved profile/JD locally and returns a PDF attachment. If the profile or JD changed since the preview, regenerate first. LaTeX downloads remain available.

PDF compilation requires Tectonic or pdfLaTeX (TeX Live/MiKTeX) on PATH. Alternatively, set `TECTONIC_PATH` to the Tectonic executable before starting the server. A portable Windows installation at `.runtime/tectonic/tectonic.exe` is also detected. Compiler binaries are not bundled in the public repository. Compilation uses temporary files, disables shell execution, limits runtime, and does not accept raw LaTeX from HTTP clients. First use may download LaTeX packages.
