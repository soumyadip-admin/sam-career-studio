# Update to PWA v5

This update repairs an empty production radar and adds the missing hourly wake-up workflow.

1. Upload/replace the visible PWA v5 files in the `sam-career-studio` repository.
2. Create `.github/workflows/hourly-refresh.yml` manually if GitHub's browser uploader omits the hidden `.github` folder.
3. Add repository secrets `APP_URL` and `APP_ACCESS_KEY`. Use the existing Render app access key; never expose it in commits, screenshots or chat.
4. Wait for Render Auto-Deploy.
5. Confirm `/api/health` reports build `2026.11.20-pwa.5`, at least 20 `active_jobs`, and a non-failed `last_scan`.
6. Run **Hourly career data refresh** once from GitHub Actions and require a green result.
7. Reopen the installed Android PWA so service worker cache v5 activates.

The scanner commits the public Sheet fallback first and then adds portal results independently. It never labels discovery as an application.
