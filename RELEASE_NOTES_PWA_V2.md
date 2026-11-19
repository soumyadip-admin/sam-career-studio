# Sam Career Studio — PWA v2 release notes

Build: `2026.11.19-pwa.2`

## Why the six old jobs no longer appear

The older fixed CRM cards were demo/search seed records, not live vacancies. Build v2 removes those exact records from SQLite and from the device-side cache. The CRM now begins empty unless the user has intentionally tracked real jobs.

## Job experience

- Live radar shows the first **20** records immediately and loads 20 more per click.
- A separate **20-job domain-transition shortlist** is regenerated from the current live database.
- Location categories: Kolkata, Bengaluru, Hyderabad, Remote and Other India.
- The shortlist prefers junior/mid-level analytics roles and puts dated source records ahead of age-unknown tracker rows.
- Call-centre, voice/chat-support, telecalling and BPO/customer-process work remains excluded.
- BPO operations experience is treated as transferable business context, not as the target domain.
- Browser data refresh: every five minutes while the app is open.
- Source discovery: hourly plus the manual Refresh now button.

## Google Sheet verification

The authorized `Job Application Tracker` was read successfully:

- Spreadsheet ID: `1X6CE7ka9rbj-2xm8YdubQ9e3rzxOk_0KCpELvKRZxEE`
- Main tab: `Job_Applications`
- Size at verification: 18,639 rows × 26 columns
- The top records include Financial Data Analyst, Business Analytics Analyst, Business Analyst, Associate Business Data Analyst, Data Analyst – Supply Chain and other analytics roles.
- The supplied timestamp is an application/tracker event, not a source posting date. The app therefore keeps Sheet records age-unknown and clearly labeled.

## Jarvis

Jarvis is a no-cost text/voice career assistant backed by the app database. Supported commands include:

- `What Data Analyst jobs are available in Kolkata?`
- `Show remote Power BI jobs`
- `Refresh jobs`
- `Open my roadmap`
- `Open my pipeline`
- `Open the ATS matcher`

Browser speech recognition and speech synthesis are used when available. Jarvis never submits an application or changes a CRM stage without the user's action.

## Roadmap

A 25-task Data Analyst transition roadmap covers:

1. Analytics, Excel, statistics and KPI fundamentals
2. SQL from joins through windows and data-quality checks
3. Power Query, star schema, DAX and dashboard storytelling
4. Python/Pandas, visualization, ETL and APIs
5. Portfolio evidence and truthful resume bullets
6. SQL/case/behavioral interview preparation and weekly applications

Progress is saved on the device and available offline.

## Validation snapshot

- Latest source run: 9 — completed, 13/13 source groups, 5,005 records seen and 337 newly inserted.
- Current source-dated jobs in past 24 hours after run: 471.
- Default shortlist: 20 current records.
- Browser QA: desktop and 390 × 844 mobile both show 20 live cards and 20 shortlist cards with no horizontal overflow or console errors.
- Offline QA: shell, 20 live cards, 20 shortlist cards and roadmap load from the cache.
- Jarvis QA: Kolkata command applied the location/role filter and returned direct application links.
- Pipeline QA: Track job created a verified live-import CRM record; the test record was then removed.
