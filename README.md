# Wealth Command Center

A working local, multi-account web application around the existing Wealth Algorithm Python engine. English, Japanese, Simplified Mandarin Chinese, Thai, Korean, and Vietnamese are included. No personal profile is preloaded.

This is **a tested first release, not the complete public product**. The roadmap from the referenced discussion includes features that need verified symbolic data, artwork/provider configuration, licensing decisions, or production infrastructure. See [scope and release gates](docs/scope.md).

## Open the local application

On this workspace, the Python 3.11 environment has already been prepared:

```powershell
.\run.ps1
```

Visit [http://127.0.0.1:8765](http://127.0.0.1:8765), create an account, and add a profile. The local guide works without an API key. This address is only on this computer; it is not a public deployment.

On another computer, install Python 3.11, then from this source folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
.\run.ps1
```

macOS/Linux:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m uvicorn wealth_command_center.app:app --host 127.0.0.1 --port 8765 --no-proxy-headers --no-access-log
```

Python 3.11 avoids needing a Windows C compiler for the pinned `pyswisseph` release. There is no frontend build step. Run from the complete source folder, since the web, registry, and vendored engine directories are runtime assets.

## What works

- Separate accounts, private profiles, saved journal/decision/experiment entries and locations, account export, and authenticated deletion APIs.
- A mobile-first Command Center with the six requested/base languages, localized controls, date/number formatting, and a public-assets-only service worker.
- Offline city-name lookup with multilingual aliases, city-center coordinates, and IANA timezone suggestions. Verify the place and exact birth location before saving.
- Natal calculations, the original custom score, numerology, optional typology, gates, custom calendar, dated transit snapshots, Mayan mappings, cardology, and Tarot.
- Touch-friendly Leaflet map, body/angle filters, saved places and comparison of notes/coordinates. No fabricated wealth-location ratings.
- A local rule-based evidence guide and opt-in Anthropic interpretation. The model reads authorized evidence; it cannot change calculations or take external actions.
- Deterministic planetary Cosmic Cards with JSON/SVG export, provenance and fingerprints. Unsupported correspondences remain absent.
- Stellarium script export and optional, disabled-by-default local RemoteControl adapter. The Python engine remains the scoring authority.
- A personal-equation experiment, separate from the original score, with explicit user-defined ratings and coefficients.
- Tested Nakshatra circular-boundary/pada algorithms and a clearly incomplete candidate catalog. The custom overlay is **not activated** with guessed degrees.
- Optional local MCP interface using explicit input only; it cannot read web accounts or their databases.

## Calculation integrity

The engine is pinned to [DuncanDuMond/Wealth-Algorithm](https://github.com/DuncanDuMond/Wealth-Algorithm/tree/1a192eeb2a182f1a32a071d1dd51163936218e2a). It is vendored under `vendor/wealth_algorithm`; integration changes repair imports, remove request-time downloads and preserve precision/provenance. The original working clone is unchanged.

The current upstream custom framework uses Lahiri sidereal positions and its own Sagittarius-first sign/house mapping. It is **not silently replaced** by a new IAU or stellar-midpoint zodiac. The proposed custom true-sky origin and epoch must be supplied and validated before that migration.

Local civil birth times are converted to UTC. Unknown, nonexistent, and ambiguous birth times produce an actionable limitation instead of invented noon charts. The current engine uses UTC as an approximation to UT; it is not a sub-second astrometric reference.

No ephemeris is downloaded during a request. The bundled fixed-star file is reused. Missing planetary files may trigger Swiss Ephemeris's Moshier fallback; missing Chiron data is an explicit omission. Reports record the actual backend and data-file hashes. Configure `WCC_EPHE_PATH` for a verified, legally obtained ephemeris directory.

Symbolic scores, mappings and interpretations are not scientifically validated wealth predictions. The interface keeps astronomical calculation, derived rules, experimental scores, and interpretation distinct. No bank connection or trade execution exists.

## Optional integrations

See [integration setup](docs/integrations.md) and `.env.example`. The application reads environment variables; it does not automatically load `.env` files.

Setting `ANTHROPIC_API_KEY` enables the consent checkbox. Only a checked query may send the question and selected evidence to that provider. No key is sent to the browser. Cloud output checks validate references and tool protocol, not the truth of every generated sentence; users must review the evidence.

Keep `STELLARIUM_ENABLED=false` on public or shared servers. Loopback refers to the API server's desktop, **not** a website visitor's computer. Script export is the cross-machine path. No embedded Stellarium Web WASM/assets are included in this release.

## Verification

The delivered snapshot passed 124 Python tests, seven interface-state tests, static checks, and the actual desktop/mobile browser workflow. See the detailed record and limits below.

```powershell
.\.venv311\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .test-temp-verification
.\.venv311\Scripts\ruff.exe check wealth_command_center tests
```

Use `.venv` instead on a new installation. `requirements-dev.txt` supplies the test tools. Browser smoke tests and their setup are documented in [verification](docs/verification.md).

The API contract is at `/openapi.json`. Read [architecture](docs/architecture.md) before adding new calculations, agent tools, or user-owned storage.

## Before public release

Do not simply expose this local server to the internet. Resolve the project/Swiss Ephemeris/Stellarium licensing choices; add managed email verification and recovery, HTTPS, secure cookies, deployment-wide quotas, backups/restore verification, data retention/deletion policy, and production security/accessibility/localization review. The included Dockerfile is a deployment starting point, not evidence that a production deployment has been tested.

Data is stored in SQLite at `data/wealth.db` by default. It is not encrypted at rest by the app; protect the host and backups. Deleting records removes them logically; old backups and SQLite pages may retain data until a documented retention/secure-erasure process runs. No account recovery email service is configured in this local release.

See [third-party notices](THIRD_PARTY_NOTICES.md). No license has been invented for the original repository or your new application.

The source archive excludes databases, credentials, runtime environments and test screenshots. `scripts/package.ps1` creates a fresh archive without overwriting an existing one.
