# Sam Career Studio PWA v3 release notes

Build: `2026.11.19-pwa.3`

## Access-key reliability

- Replaced simultaneous browser password prompts with one in-app private-access dialog.
- The key is verified before protected API requests begin and then stored only in that browser/device's local storage.
- Incorrect keys remain in the dialog with a clear error instead of repeatedly reopening prompts.
- Added **Change device key** inside Jarvis.
- The dialog explicitly warns that the app key is not a Gmail, GitHub or phone password.
- Updated the service-worker cache to `sam-career-pwa-2026-11-19-3` so installed Android copies receive the fix.

## Jarvis task-agent upgrade

Jarvis remains a no-cost, database-grounded task agent rather than an unrestricted large-language-model chatbot. It now supports:

- comparing up to five current jobs by role and location;
- explaining why a selected result may fit the saved transition profile;
- follow-up references such as “the first one”;
- seven-day role-specific interview preparation plans;
- common-skill and profile-gap summaries for two or three pasted JDs separated by `---`;
- opening the ATS matcher for grounded, JD-specific resume analysis;
- preparing selected jobs for the Interested stage and saving them only after an explicit confirmation button;
- refusing to submit applications or contact employers automatically;
- existing location/role searches, roadmap, pipeline, ATS and source-refresh commands.

## Verified behavior

- One fresh-device access dialog; correct key loads all protected content without repeated prompts.
- Incorrect key is rejected in place.
- 16 project cards load after authentication.
- 390 px mobile layout has no horizontal overflow.
- A five-job Kolkata comparison, first-result explanation and two-job confirmation flow passed browser QA.
- No job is added before confirmation; two confirmed records reached Interested and were removed after QA.
- Python, JavaScript and database integrity checks passed.
