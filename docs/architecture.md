# Architecture and extension rules

```text
Wealth Command Center (six-language mobile web UI)
             |
  Same-origin FastAPI + account ownership
             |
   Canonical Python service + one Swiss lock
       /          |          \
   Reports      GeoJSON     SkyViewState
      |            |           |
  Evidence       Leaflet     Stellarium adapter
   /     \
Agent   CosmicCard resolver -> VisualSpec -> SVG
```

`app.py` owns authentication, authorization, request validation and quotas. `store.py` owns transactional SQLite data. Every profile/journal query includes the current owner. Sessions contain random opaque tokens; only token hashes are stored. Passwords use salted scrypt. Same-site HTTP-only cookies, same-origin mutation checks and a required request header protect browser writes.

`engine.py` is the sole application calculation gateway. All Swiss global state (ephemeris path, sidereal mode and observer) is reset and locked per calculation. Its imported engine modules are pinned upstream source, not a frontend reimplementation. Presentation trimming occurs after score computation. The current-day transit snapshot is separate from the natal score and is not an event-search algorithm.

`agent.py` receives an already-authorized report, not a database handle. Its tools can read bounded evidence and submit interpretations only. Its calls have round/token/time limits, explicit cloud consent and an honest local fallback. Account management, journal writes and Stellarium control remain explicit UI/API actions.

`cosmic_cards.py` separates canonical body identity, chart placement, symbolic correspondences, provenance and visual layout. Missing custom correspondence facts remain null. Canonical facts never come from image-generation prompts. New renderer styles must not modify the input report.

`equation.py` implements the conversation's formula as an uncalibrated, user-configured experiment, never as a replacement financial forecast. `boundaries.py` implements frame-tagged circular geometry independently of the live zodiac. The unverified 27-group registry is not a deployable degree table.

## Adding a feature

1. Define inputs, output schema, evidence IDs, uncertainty and ownership requirements.
2. Reuse or extend the Python domain function; never compute the same astronomy in JavaScript, the LLM or Stellarium.
3. Add a boundary test and real-engine integration test, including invalid and missing inputs.
4. Add UI copy to every locale, test mobile layout and keyboard access.
5. Mark incomplete external integrations explicitly and update the scope matrix.

## Deliberate implementation choices

FastAPI/Pydantic, SQLite, Leaflet, plain browser modules and local city data keep this first slice runnable without separate infrastructure. React/Next.js, PostgreSQL, a distributed worker queue, generic agent orchestration frameworks and a vector database were recommendations, not requirements to install all at once. Stable HTTP/data boundaries permit later migration without duplicating the engine.

No automatic forecast learning, automated financial action, production signup email, client-side private offline database, or full image-generation provider is implemented. A service worker only caches public presentation resources; authenticated API calls always go to the server.
