# Sam Career Studio

A responsive, source-aware career command center for **Soumyadip Sarkar (Sam)**. It combines public job discovery, a six-stage application CRM, an evidence-first resume studio, 16 portfolio blueprints, skills tracking and interview practice.

## What is implemented

- **Premium cyber-dark interface** with a locally served Three.js 3D orbit/particle background.
- **10-portal search matrix** across profile-fit non-call-centre roles and four target locations.
- **Hourly job scanner** with a past-24-hours default view, optional 72-hour view, run history, URL deduplication, provenance and automatic expiry.
- **Deduplicated public Google Sheet supplement:** recent rows from the supplied Job Application Tracker are imported as age-unknown tracker events, never misrepresented as freshly posted vacancies.
- **Android-installable PWA:** manifest, app icons, service worker, install control, cached read access and a device-side CRM cache for travel use.
- **Live named-portal feeds:** LinkedIn, Naukri, Indeed India, Glassdoor India and Shine dated public results, plus Instahyre's public API (clearly labeled because it does not expose posting age).
- **Supplemental free public feeds:** direct employer Lever/Greenhouse boards, Remotive, Jobicy, Arbeitnow, RemoteOK and Himalayas.
- **Preference enforcement:** call-centre, voice/chat process, telecalling and BPO-process roles are excluded; salary is never used as a cap.
- **20-job live transition shortlist:** current analytics roles ranked separately from the user-controlled CRM, with Kolkata, Bengaluru, Hyderabad, Remote and Other India categories.
- **Six-stage Kanban CRM:** Interested, Applied, Assessment, Interview, HR Round and Selected; obsolete permanent demo cards are removed.
- **Jarvis voice/text assistant:** finds location/role-specific jobs, opens the roadmap/CRM/ATS and can trigger a refresh using browser speech recognition at no API cost.
- **Data Analyst transition roadmap:** 25 device-saved tasks spanning fundamentals, SQL, Power BI, Python, portfolio evidence and interviews.
- **16 differentiated project blueprints:** Excel, Power BI/DAX, SQL and Python tabs, copy control and checked dataset-source links.
- **Daily project inspiration signal** from recently updated public GitHub repositories.
- **Persistent SQLite data:** profile, jobs, live results, portals, roles, projects, trends, skills, interview Q&A and scan runs.
- **Evidence-first Resume Studio:** paste a real JD, compare supported/partial/missing requirements, and download a single-column DOCX or PDF tailored only from the supplied resume. Startek is corrected to Dec 2025–Sep 2026.
- **Skills sliders, interview simulator, CSV export and JD-specific ATS-style analysis** with an analysis fingerprint, scoring version, weighted breakdown and truth-safe evidence guidance.
- Responsive layouts tested at desktop and 390px mobile widths.

## Data-integrity policy

This app does not claim that all ten target portals are scraped.

- **Live dated feed** means a posting was fetched from a public page/API with a source-supplied posting date and original URL.
- The default radar includes only source-dated listings from the past **24 hours**; a 72-hour view remains available.
- **Current, age unavailable** means the public source currently returns the vacancy but does not expose its posting date; these records require the optional freshness filter.
- **Search launcher** means the control opens a targeted portal search but does not ingest or claim vacancies from that portal.
- Salaries are displayed only when a source supplies them; none are inferred and there is no salary cap.
- Call-centre/BPO process exclusions are applied before a record becomes active.
- The profile match and Resume Studio readiness percentage are transparent diagnostics, not hiring probabilities or real employer ATS scores. No ATS pass or interview is guaranteed.
- Resume tailoring reorders supported evidence; missing skills are reported and never inserted.
- GitHub project trends are inspiration signals, not evidence that a project is frequently asked in interviews.
- Portal availability, rate limits and posting freshness can change. Always verify on the original source before applying.

This separation is intentional: bypassing anti-bot controls or presenting search results as verified live data would be unreliable and misleading.

### Named portal access audit

| Portal | Current implementation | Reason |
|---|---|---|
| LinkedIn | Live public dated results | Public guest results adapter |
| Naukri | Live public dated results | Open-source JobSpy public search adapter |
| Indeed India | Live public dated results | Open-source JobSpy public search adapter |
| Glassdoor India | Live public dated results | Open-source JobSpy public search adapter |
| Shine | Live public dated results | Server-rendered public search cards |
| Instahyre | Live current results; age separated | Public API omits posting date |
| Foundit | Targeted launcher | Public page exposes no stable unauthenticated dated-listings API |
| Cutshort | Targeted launcher | Public job endpoint is not available without controlled application state |
| Wellfound | Targeted launcher | Public page does not expose a stable dated search feed |
| SimplyHired India | Targeted launcher | Security/access-control response |

A paid/authorized provider can be added later for the four launcher-only portals. Gmail API credentials are **not required** for the selected dashboard-only alert mode.

## Run locally

### Windows / Edge app mode

Double-click:

```text
launch_windows.bat
```

Or run manually:

```powershell
py -m pip install -r requirements.txt
py init_db.py
py server.py
```

Then open `http://127.0.0.1:8000` or launch:

```powershell
msedge.exe --app=http://127.0.0.1:8000 --window-size=1600,950
```

### Linux/macOS

```bash
chmod +x start.sh
./start.sh
```

## Automation behavior

- A first source refresh starts when the server starts and no prior refresh exists.
- The scheduler checks every five minutes and executes a refresh when the last successful scan is at least one hour old.
- Bangalore and Kolkata are checked every run; Hyderabad/India-wide roles also arrive through direct public feeds and the supplied tracker. Remote public APIs refresh hourly.
- Manual **Sync jobs** uses the same scanner and lock, so scans cannot overlap.
- For uninterrupted hourly automation, `server.py` must run on an always-on machine or hosted service. A browser tab alone cannot execute backend schedules.
- Source-dated records older than 72 hours are hidden. Undated current results become inactive if not re-seen within six hours.
- The public jobs Sheet is fetched each run, mapped from its explicit 11-column schema, limited to recent records and deduplicated by canonical URL. Its timestamp is a tracker/application event and is never used as a posting date.
- A sleeping free host cannot run an in-process timer. The included GitHub Actions workflow wakes the deployment and triggers the refresh hourly.

## API highlights

| Endpoint | Purpose |
|---|---|
| `GET /api/metrics` | Current job, pipeline, project and skill metrics |
| `GET /api/portals` | Ten labeled search launchers |
| `GET /api/scraper/live` | Filtered active listings plus location/source counts |
| `GET /api/recommendations` | Live 20-job domain-transition shortlist |
| `POST /api/jarvis` | Voice/text assistant command engine backed by the live database |
| `POST /api/scraper/scan` | Start a non-overlapping background refresh |
| `GET /api/scraper/status` | Run state, coverage and source limitations |
| `GET/POST /api/jobs` | Pipeline records |
| `PATCH /api/jobs/{id}` | Move a lead or update notes |
| `GET /api/projects` | All 16 project blueprints |
| `GET /api/project-trends` | Daily GitHub inspiration signal |
| `GET/PATCH /api/skills/{id}` | Persistent self-assessments |
| `GET /api/interview` | Curated practice bank |
| `POST /api/ats_match` | Truth-safe JD keyword coverage |
| `POST /api/resume/analyze` | Resume/JD evidence and gap analysis |
| `POST /api/resume/download` | Generate protected DOCX or PDF resume download |
| `GET /api/export/jobs.csv` | Download pipeline CSV |

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Project structure

```text
career_engine/
├── init_db.py             # schema, profile and seed content
├── scanner.py             # public-source adapters and hourly scanner
├── server.py              # FastAPI backend and scheduler
├── resume_engine.py       # truthful JD analysis and DOCX/PDF generation
├── career_engine.db       # persisted SQLite database
├── templates/index.html   # complete single-page frontend
├── static/
│   ├── app.js             # application interactions and device-side CRM cache
│   ├── scene.js           # Three.js scene
│   ├── styles.css         # responsive visual system
│   ├── three.min.js       # local Three.js build
│   ├── manifest.webmanifest
│   ├── sw.js              # offline/read cache and installability
│   └── icons/             # Android/PWA icons
├── .github/workflows/hourly-refresh.yml
├── render.yaml
├── DEPLOY_PWA.md
├── MOBILE_APP_GUIDE.md     # beginner-friendly Android install and old-build cleanup
├── requirements.txt
├── launch_windows.bat
└── start.sh
```

## Android PWA deployment

The Android phase is implemented as an installable PWA. Deploy it over HTTPS, open it once in Android Chrome and use **Install app**. The recommended ₹0 Render + GitHub Actions setup, its free-tier persistence limits and exact installation steps are documented in [`DEPLOY_PWA.md`](DEPLOY_PWA.md).

When `APP_ACCESS_KEY` is set on the host, personal API endpoints require that key. The PWA prompts once and stores it only in that device's local browser profile.
