# Update the deployed app to PWA v3

This update fixes repeated access-key prompts and upgrades Jarvis.

1. Extract `sam-career-studio-pwa-v3-update.zip` on Windows.
2. Open `https://github.com/soumyadip-admin/sam-career-studio`.
3. Choose **Add file → Upload files**.
4. Open the extracted update folder, press **Ctrl+A**, and drag all selected contents onto GitHub.
5. GitHub should show modified files under `static`, `templates`, and `server.py`.
6. Commit directly to `main` with message `Upgrade access and Jarvis to PWA v3`.
7. Render automatically deploys the commit. Wait until the service shows **Live**.
8. Open `https://sam-career-studio.onrender.com/api/health` and confirm the build is `2026.11.19-pwa.3`.
9. On Android Chrome, close and reopen the installed app. If necessary, refresh twice so the new service worker activates.
10. Enter the latest Render `APP_ACCESS_KEY` once in the in-app unlock dialog. It will remain on that device until site data is cleared or **Change device key** is selected.

Never upload or reveal the APP_ACCESS_KEY. No database file or secret is included in this update package.
