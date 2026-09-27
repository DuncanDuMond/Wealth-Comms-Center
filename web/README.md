# Wealth Command Center web interface

The web client is a same-origin, dependency-free ES-module application. The server serves `index.html` at `/`, this directory at `/assets`, and the public service worker at `/sw.js`. Leaflet is vendored locally; map boundaries and the city lookup are local. There is no browser-side astronomy engine and no third-party analytics, font, tile, or geocoding request.

## Surface and data boundaries

- Six interface languages: English, Japanese, Simplified Chinese, Thai, Korean, Vietnamese. UI labels, forms, number/date formatting, planets, signs, and derived chart points are localized. Original algorithm field names, source evidence, and some engine warnings retain their source language so the UI does not silently reinterpret the calculation. Native-language copy review remains advisable before public release.
- Register/sign in, owned profile creation/editing/deletion, verified timezones, optional unknown time, offline city lookup, manual coordinates, and account export. No preloaded personal profile exists.
- Overview, inspectable evidence and provenance, symbolic systems, local vector astrocartography, body/angle filtering, saved places and non-ranking comparison, optional Stellarium script export and configured local desktop action, card previews/downloads.
- User-owned reflection/decision/experiment journal and optional, explicitly uncalibrated personal-equation experiment. Follow-up observations are new entries, preserving the original record.
- Evidence guide; sending a question to configured cloud AI requires an unchecked-by-default consent checkbox for each submission. Chat text is escaped and stays in memory for the current profile/session, not in browser storage.
- Browser storage contains only the language preference and current owned profile identifier. The service worker caches only an explicit allowlist of public static assets, not HTML navigations, private APIs, or birth data. A server connection is required for authentication/calculations; this is not an offline-calculation app.
- Account epochs discard stale private responses before/after JSON parsing. Logout and session expiry clear profile data, report, chat, journal, follow-up drafts, selected places, and experiment state. A stale 401 from one account cannot log out another account.

## Verification

From the project root, run `node --test tests/browser-state.test.mjs` for localization parity, private state clearing, delayed cross-account requests, stale 401s, body-read races, input limits, cloud consent default, selected report date, and the service-worker boundary. `node --check web/app.js` checks syntax. The integration owner's `tests/e2e.cjs` exercises real browser/server workflows.

The UI uses system fonts, native forms, semantic tables, visible focus, translated navigation names, a keyboard-accessible city lookup, responsive navigation, large touch targets, and reduced-motion preferences. Map line exploration is pointer/touch-oriented; the city lookup and saved-place list provide keyboard alternatives for selecting locations. No claim of a full external accessibility audit is made.
