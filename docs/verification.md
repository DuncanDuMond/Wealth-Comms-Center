# Verification record

Local checks were executed on Windows with Python 3.11.16. The browser workflow uses headless Microsoft Edge through Playwright. No real person's profile was used; synthetic test accounts were deleted by the test teardown.

Final local result (2026-09-26): **124 Python tests passed; seven Node interface-state/privacy tests passed; Ruff and JavaScript syntax checks passed; the full desktop/mobile browser workflow passed.** The database contained zero remaining accounts after teardown. These results are for this source snapshot, not a certification of production readiness.

## Evidence

- Actual Swiss Ephemeris calculations checked for UTC conversion, DST gaps/overlaps, polar limitations, backend/fallback reporting, body positions, map geometry/seam splitting, and concurrent profile calls.
- SQLite/API isolation checked with two accounts, unauthorized access, session invalidation, transactional writes, profile/journal cascades, exports, cross-origin writes, oversized input and sensitive validation errors.
- Six-language agent templates and Cosmic Card outputs checked, along with SVG escaping and golden fingerprints.
- Anthropic boundary tested with mocked provider responses: consent, bounded tools, unread/invalid evidence rejection and honest fallback.
- Stellarium boundary tested with mocked HTTP: safe body selection, script construction, loopback-only destinations, time/location verification and partial-failure reporting.
- MCP SDK 1.30.0 tested through a real stdio subprocess: initialization, capability resource, tool listing, actual engine call, structured results and rejection of unsupported tropical mode.
- City searches tested with Japanese, Chinese, Thai, Korean and Vietnamese names against the installed offline data.
- Personal equation arithmetic, bounds and invalid coefficients checked separately from the natal score.
- Browser workflow checked signup, profile creation, real report, all six locales, map rendering, saved location, journal, local guide, SVG export, private data export and mobile layout without horizontal overflow.
- The extended browser workflow also checked multilingual city search, equation calculation and explicit saving, plus the loaded Japanese Cosmic Card preview.
- Interface-state regressions checked draft removal on logout, stale profile responses across account switches, late unauthorized responses, response-body parsing races, locale key parity, consent defaults and service-worker exclusions.

## Repeat the checks

```powershell
.\.venv311\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .test-temp-verification
.\.venv311\Scripts\ruff.exe check wealth_command_center tests
node --test tests/browser-state.test.mjs
```

For a fresh environment, install `requirements-dev.lock` with `--require-hashes`. The optional MCP test is skipped if `mcp` is not installed. Installing `mcp>=1.20,<2` enables its real transport check.

With the server running on port 8765, install the development Node dependency and browser, then:

```sh
npm install
npx playwright install chromium
npm run test:browser
```

Set `PW_CHANNEL=msedge` to test an installed Edge browser instead, and `WEALTH_TEST_URL` for another local port. The test must only target an authorized test instance; it creates and deletes synthetic accounts. Screenshots go to `test-results`, not to a shared/public store.

## Not verified or not released

No paid Anthropic request was made. No installed Stellarium desktop was available for a live rendering check. No Stellarium Web WASM build or sky dataset is shipped. Real iOS/Android devices, native-speaker review, screen-reader audit, Docker build, hosted CI and production deployment remain unverified. A passing mock transport test is not represented as a live external integration test.

The installed FastAPI/Starlette test client currently reports deprecation notices about its HTTPX integration. They do not fail tests; track upstream migration before the next dependency update.
