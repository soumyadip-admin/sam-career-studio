# Sam Career Studio PWA v4 release notes

Build: `2026.11.19-pwa.4`

## Free-host 502 recovery

Render Free services can temporarily return 502/503/504 while waking from idle or restarting. PWA v4 handles those responses without immediately presenting a raw request failure:

- protected API requests automatically retry with bounded backoff for about one minute;
- one clear “server is waking” notice replaces repeated technical errors;
- the access-key verifier uses the same wake-up retry path;
- the service worker falls back to the most recent cached page when a navigation receives a server-side 5xx response;
- cached GET API data can be used when the same request temporarily receives a 5xx response;
- failed writes remain visible as failures after the retry budget, and the app never claims an application was submitted.

This improves the installed app during Render cold starts but cannot remove the underlying Free-plan wake-up delay. A first visit with no existing PWA cache can still show Render's loading screen until the service starts.
