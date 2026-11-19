# Install Sam Career Studio on Android — step by step

This build is a **Progressive Web App (PWA)**. It is installed from a secure HTTPS website; the ZIP is source/deployment code, not an APK.

## Important: stop using the old desktop build

The desktop screen with six fixed cards (Amazon, Concentrix, Startek, Alorica, Teleperformance and Genpact) is an older build. The current app footer must say:

`PWA build 2026.11.19-pwa.3`

The new build removes permanent demo/search cards. It has:

- a live radar that initially shows 20 jobs;
- a separate live 20-job domain-transition shortlist;
- location categories for Kolkata, Bengaluru, Hyderabad, Remote and Other India;
- an application CRM that contains only jobs you intentionally track;
- Jarvis text/voice commands; and
- a device-saved Data Analyst roadmap.

## Part A — deploy free HTTPS hosting

Android Chrome requires HTTPS for a normal PWA installation. Render Free supplies the HTTPS URL.

### 1. Prepare GitHub

1. Sign in at https://github.com.
2. Choose **New repository**.
3. Name it `sam-career-studio`.
4. A public repository is simplest for the free scheduled workflow.
5. Open the repository and choose **Add file → Upload files**.
6. Unzip `sam-career-studio-pwa-v2.zip` on your computer.
7. Open the extracted `career_engine` folder and upload its **contents** so `render.yaml`, `server.py`, `static`, `templates` and `.github` are at the repository root.
8. Commit the files.

### 2. Deploy with Render Free

1. Sign in at https://render.com.
2. Choose **New → Blueprint**.
3. Connect the `sam-career-studio` GitHub repository.
4. Render reads `render.yaml`; approve the web service.
5. For `APP_ACCESS_KEY`, enter a private passphrase that you can type on your phone. Do not commit it to GitHub.
6. Choose the Free plan and deploy.
7. Wait for the status to become **Live**. A free cold start can take about one minute.
8. Copy the Render URL, for example `https://sam-career-studio.onrender.com`.
9. Open `https://YOUR-URL/api/health`. Check that it says `"build":"2026.11.19-pwa.3"`.

### 3. Enable hourly refresh while the free service sleeps

1. In GitHub, open the repository.
2. Go to **Settings → Secrets and variables → Actions**.
3. Add a repository secret named `APP_URL` with the Render URL and no trailing slash.
4. Add `APP_ACCESS_KEY` with exactly the same passphrase used in Render.
5. Open **Actions → Hourly career data refresh → Run workflow**.
6. Confirm the workflow passes. It then runs hourly at minute 17 UTC.

The dashboard's **Refresh now** button can request an immediate refresh. Hourly is near-real-time for this free, policy-compliant system; it is not second-by-second scraping.

## Part B — install on Android

1. On Android, open **Google Chrome**.
2. Visit the Render HTTPS URL. Do not open the ZIP file in Chrome.
3. Enter your `APP_ACCESS_KEY` when asked.
4. Wait until the live radar and the 20-job shortlist load once.
5. Tap **Install app** in the app header.
6. If that button is not visible, tap Chrome **⋮ → Add to Home screen → Install**.
7. Confirm the installation.
8. Find **Sam Career** on the Android home screen/app drawer and open it.
9. Open Jarvis, tap the microphone and allow Chrome's microphone permission when prompted. Say or type `What Data Analyst jobs are available in Kolkata?`.

## If Android still shows old jobs

1. Confirm the footer build is `2026.11.19-pwa.3`.
2. Close all tabs for the old site.
3. In Chrome open **Settings → Site settings → Data stored**.
4. Find the old Sam Career URL and choose **Clear & reset**.
5. If an older PWA is installed, long-press its icon and uninstall it.
6. Reopen the new Render URL, refresh once and install again.

Build v2 also removes old `search_lead` cards from the device cache automatically. Real manual and source-imported CRM records are preserved.

## How jobs work in build v2

- **Live radar:** up to 500 results can be filtered; the first 20 are shown immediately.
- **20-job shortlist:** current analytics/domain-transition roles ranked from live sources; changes when hourly source data changes.
- **CRM:** initially empty by design. Tap **Track job** or **+ Pipeline** to add a real vacancy to Interested, then move it through the stages yourself.
- **Google Sheet:** deduplicated supplemental records are used. Its timestamp is an application/tracker event, not a posting date, so the app labels it honestly.
- **Kolkata:** Jarvis and the location filter show the current Kolkata count. There may honestly be fewer than 20 suitable Kolkata jobs at a given moment; the all-location shortlist still provides 20 when available.
- **Exclusions:** voice, chat-support, telecalling, call-centre and BPO/customer-process roles remain excluded. Prior BPO operations experience is used only as transferable analytics context.

## Offline and free-host limits

- The app shell, recently loaded GET data, roadmap progress and device pipeline cache remain available with weak connectivity.
- New scans, ATS analysis, external application links and synchronization need internet access.
- Render Free sleeps and uses an ephemeral local filesystem. Export the CRM CSV regularly. The device cache protects the installed phone's copy but is not guaranteed multi-device database synchronization.
