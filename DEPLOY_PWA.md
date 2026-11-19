# Deploy and install Sam Career Studio on Android for ₹0

> Current build: `2026.11.19-pwa.3`. For a beginner-friendly phone walkthrough and old-build cleanup steps, read `MOBILE_APP_GUIDE.md` first.

## Recommended no-cost setup

Use one **Render Free web service** for the FastAPI/PWA and the included **GitHub Actions hourly workflow** to wake it and request a refresh. Render supplies HTTPS, which Android/Chrome requires for PWA installation.

This is the best zero-cost prototype route, but it has two honest limitations:

1. Render Free sleeps after inactivity, so the first open can take about a minute.
2. Render Free has an ephemeral filesystem. SQLite changes can be lost after a spin-down, restart or redeploy. The installed PWA therefore keeps a device-side pipeline cache so travel use remains available on that Android device. Use **Export CSV** regularly. A future durable multi-device CRM needs external persistent storage or a paid disk/database.

The public Job Application Tracker Sheet is fetched hourly without credentials. Its timestamp is treated as an application/tracker event—not a vacancy posting date.

## 1. Put this folder in a GitHub repository

Create a repository and upload the contents of `career_engine/`, including:

- `render.yaml`
- `.github/workflows/hourly-refresh.yml`
- `server.py`, `scanner.py`, `init_db.py`
- `templates/`, `static/` and `career_engine.db`

A public repository gets the simplest no-cost scheduled Actions allowance. If the repository is private, GitHub usage limits apply to your account.

## 2. Deploy on Render

1. Sign in at `https://render.com/`.
2. Choose **New → Blueprint**.
3. Connect the GitHub repository.
4. Render detects `render.yaml`.
5. When asked for `APP_ACCESS_KEY`, enter a long private passphrase. Do not commit it to GitHub.
6. Deploy and wait for a URL similar to `https://sam-career-studio.onrender.com`.
7. Open `<your-url>/api/health`. It should show build `2026.11.19-pwa.3`.

The app asks for the same access key on first use and stores it only in that browser/PWA profile.

## 3. Enable the hourly GitHub refresh

In the GitHub repository, open **Settings → Secrets and variables → Actions** and create:

- `APP_URL` — the Render URL without a trailing slash
- `APP_ACCESS_KEY` — exactly the same secret configured on Render

Open **Actions → Hourly career data refresh → Run workflow** once. Confirm that all three steps pass. The included schedule runs at minute 17 of every hour (UTC).

The FastAPI scheduler also checks hourly while the service is awake. The GitHub workflow is needed because a sleeping free service cannot run its own timer.

## 4. Install on Android

1. Open the Render HTTPS URL in Chrome on Android.
2. Enter the app access key when prompted.
3. Wait for the home page and current jobs to load once; this also fills the offline cache.
4. Tap **Install app** in the header. If Chrome does not show it, use **⋮ → Add to Home screen → Install**.
5. Launch **Sam Career** from the home screen.

Cached pages, the most recently loaded GET data, and the device-side pipeline remain available when connectivity is weak. Refreshes, ATS requests and server synchronization need internet access.

## Data-source truth notes

- **Today** means a source supplied a posting date within the past 24 hours.
- **Past 72 hours** means a source supplied a posting date within that window.
- **Google Sheet Tracker** records are deduplicated by canonical URL and always say that posting age is unavailable.
- If all strict dated feeds are temporarily empty, the UI may show a clearly labeled Sheet fallback instead of a misleading blank screen.
- Call-centre, voice/chat process, telecalling, customer-process and BPO-process roles remain excluded.
- Salary is never used as a cap.

## Google authorization boundary

The Arena Gmail and Google Sheets connection used during development is not exported into this app. Runtime reading works for the public jobs sheet. The private **Gmail AI Tracker** sheet and Gmail mailbox require a separate production OAuth/service-account design before automatic runtime synchronization can be enabled safely.
