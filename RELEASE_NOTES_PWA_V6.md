# SAM Career Studio — PWA v6 Resume Studio

Build: `2026.11.20-pwa.6`

## Added

- New top-navigation **Resume** tab.
- Job-title, company, source-URL and full-JD inputs.
- Deterministic requirement extraction with matched, partial and missing evidence.
- Evidence-first ATS readiness diagnostic with visible scoring formula.
- Original-versus-tailored supported-keyword visibility.
- One-click ATS-safe DOCX and PDF generation.
- Single-column standard-heading documents without tables, icons, photos or text boxes.
- Corrected Startek employment dates: **December 2025 to September 2026**.
- Privacy protection through the existing app access-key middleware.

## Truthfulness controls

- The supplied PDF resume is the only factual baseline for resume content.
- Missing skills are shown as gaps and never inserted into generated resumes.
- The engine never claims an ATS pass, interview, application or recruiter outcome.
- The generated file must still be reviewed before applying.

## Validation

- 12 automated engine/UI/scanner tests passed.
- 25 real job descriptions were analyzed.
- 25 DOCX and 25 PDF resumes were generated and validated.
- All 25 PDFs are one-page documents.
- Corrected Startek dates appeared in all 50 outputs; the old May 2026 end date appeared in none.
- Unsupported hard-skill leakage checks passed for all 25 trials.
- Analyze and DOCX/PDF download endpoints passed an end-to-end HTTP test.
