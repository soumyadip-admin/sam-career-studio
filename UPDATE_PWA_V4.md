# Update to PWA v4

This small reliability update handles temporary Render Free 502/503/504 responses.

1. Extract `sam-career-studio-pwa-v4-update.zip`.
2. Open `https://github.com/soumyadip-admin/sam-career-studio`.
3. Choose **Add file → Upload files**.
4. Drag all contents from the extracted folder into GitHub.
5. Commit directly to `main` with message `Add automatic recovery for Render cold starts`.
6. Wait for Render to deploy automatically.
7. Confirm `https://sam-career-studio.onrender.com/api/health` reports build `2026.11.19-pwa.4`.
8. Close and reopen the installed Android app, then refresh once. Reinstallation is not required.

The app will retry temporary server errors for about one minute and use cached GET data where available. It does not conceal permanent failures or claim that a write succeeded when it did not.
