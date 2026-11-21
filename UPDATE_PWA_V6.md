# Deploy PWA v6 Resume Studio

This update adds the new Resume tab and does not change any secret values.

## Files added

- `resume_engine.py`
- `tests/test_resume_engine.py`
- `tests/test_resume_ui_contract.py`
- `scripts/run_resume_trial.py`
- `RELEASE_NOTES_PWA_V6.md`
- `UPDATE_PWA_V6.md`

## Files changed

- `server.py`
- `requirements.txt`
- `templates/index.html`
- `static/app.js`
- `static/styles.css`
- `static/sw.js`
- `static/manifest.webmanifest`

## Beginner deployment

1. Back up the current repository or keep the existing complete backup ZIP.
2. Upload the contents of the PWA v6 deployment ZIP to the root of the `sam-career-studio` GitHub repository, replacing files with the same names.
3. Commit directly to `main` with the message: `Add evidence-first Resume Studio`.
4. Wait for Render to deploy and install the two added dependencies.
5. Open `/api/health` and confirm build `2026.11.20-pwa.6`.
6. Open the installed PWA. If the old menu remains, close it completely and reopen it; the v6 service-worker cache will replace v5.
7. Open **Resume**, paste a real JD, analyze it, then test both download buttons.
8. Run GitHub Action **Hourly career data refresh** and require a green result.

## Important

- Keep existing GitHub and Render secrets unchanged.
- Do not upload the user's original PDF to the public repository.
- Generated resumes are available only through protected `/api/` endpoints when `APP_ACCESS_KEY` is configured.
- No ATS pass or interview is guaranteed.
