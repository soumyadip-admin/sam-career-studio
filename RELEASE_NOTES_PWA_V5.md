# Sam Career Studio PWA v5 release notes

Build: `2026.11.20-pwa.5`

## Empty-radar repair

- The public Google Sheet fallback is fetched and committed before slower portal scans.
- Each source is saved independently; a blocked or memory-heavy portal cannot roll back already collected jobs.
- Sources run sequentially to stay within the Render Free memory budget.
- The public health endpoint now exposes secret-free active-job and latest-scan counts so an empty radar is diagnosable.
- The hourly workflow fails unless at least 20 active jobs are present.

## Quality repair

- Overseas jobs returned by broad searches are rejected unless the role is genuinely worldwide/anywhere remote.
- Broad APAC/Asia labels are not treated as proof of India eligibility.
- Only target Data Analyst, BI, MIS, reporting, WFM and operations-analytics transition titles remain active.
- Employer-board ingestion filters before storing to reduce memory and noise.
- Empty-state controls now hide the “Show 20 more jobs” button correctly.

No applications are submitted automatically. Google Sheet timestamps remain tracker/discovery events, not vacancy-posting dates.
