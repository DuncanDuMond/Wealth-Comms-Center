# Agent and sky integrations

The Wealth Command Center calculation engine owns the facts. The guide, card
renderer, and Stellarium adapters consume those facts; none runs a second version
of the scoring algorithm. The sky viewer cannot change a score.

## Agent

The built-in local guide works without a paid API or network connection. It has
Japanese (`ja`), Simplified Chinese for Mandarin readers (`zh-CN`), Thai (`th`),
Korean (`ko`), Vietnamese (`vi`), and English (`en`) templates. It explains the
symbolic score and provides topic-specific map, cycle, provenance, and journaling
guidance. It is deliberately labeled as a rule-based guide, not a language model.

For optional conversational AI, set `ANTHROPIC_API_KEY` on the server and optionally
`ANTHROPIC_MODEL`. The default is `claude-sonnet-5`, checked against the
[official model documentation](https://platform.claude.com/docs/en/models/sonnet-5/overview)
on 2026-09-26. Availability still depends on the operator's provider account.
No live paid API call was required to build or test this integration.

The caller must also explicitly set `allow_cloud=True` on `respond` (the HTTP API
uses per-request consent). A configured key alone does not transmit personal data.
Cloud mode sends the question, a bounded conversation history, and the relevant
computed evidence to Anthropic. It does not send the account object or whole birth
profile. Questions can themselves contain personal data: explain this to users.
Do not include other users' histories. The API must authorize report ownership
before it invokes the guide.

The model may read up to eight evidence items at a time and submit a cited answer.
Only IDs actually present and read from the authorized report are accepted. The
whole run is limited to three requests, 1,200 output tokens per request, and a
30-second wall-clock budget between calls. Network operations have bounded
timeouts. Invalid answers and unavailable providers transparently fall back to
the local guide. Existence-checked citations are not proof that every sentence is
true; provider interpretations remain visibly labeled and require human review.
The agent has no persistence, shell, general network, trade, or desktop-control
tool. Suggested actions are saved only through the user's separate journal action.

## Stellarium desktop

Two concrete integration paths are implemented:

1. Export a `.ssc` script and run it yourself in Stellarium. This works without a
   running local control service. The script freezes time, sets the Earth observer,
   selects a physical body and centers it. It does not auto-launch an application.
2. On a **local/private installation only**, enable Stellarium's RemoteControl
   plugin, then set `STELLARIUM_ENABLED=true`,
   `STELLARIUM_URL=http://127.0.0.1:8090` and optionally `STELLARIUM_PASSWORD`.
   Use the explicit desktop-sync action. Do not expose this feature on a public
   multi-user server: the viewer is shared and loopback means the server computer,
   not a visitor's phone.

The adapter accepts only literal loopback origins (or `localhost`, pinned to
127.0.0.1), does not follow redirects, ignores environment proxies, serializes
updates, and never calls Stellarium's arbitrary-script endpoint. It posts
location fields in degrees/meters, then the **engine-provided** Julian day with
`timerate=0`, then the allowlisted body's English name to `main/focus`. It checks
the reported time/location afterward. A partial failure is reported, not hidden.
No raw remote output or password is returned to the caller.

The contract is `sky_state` version 1.0: timezone-aware `utc`,
`julian_day_utc`, `latitude`, `longitude`, and `altitude`. The current engine's
Julian day uses UTC as the UT input approximation; this is not a claim of UT1/TT
time-scale equivalence or sub-second cross-engine agreement. The script uses UTC
calendar fields while RemoteControl uses the engine's Julian day. Only physical
bodies are supported. Lots, gates, Selena, archetypes and other symbolic points
must not be passed off as visible celestial objects.

This follows the official [RemoteControl API](https://stellarium.org/doc/head/remoteControlApi.html)
and [script API](https://stellarium.org/doc/1.x/classStelMainScriptAPI.html).
Tests exercise HTTP request shapes, state verification, local-only controls and
input escaping using a simulated HTTP boundary. A real installed Stellarium and
rendered pixels have not been verified here.

## Stellarium Web Engine: deliberately optional

The [official Web Engine](https://github.com/Stellarium/stellarium-web-engine)
is a separate WebAssembly renderer. This application does not ship a compiled
engine or claim that an embedded planetarium is finished. Before adding one:

1. Decide the deployment/license obligations for the AGPL engine and its data.
2. Build and pin its JS/WASM artifacts, validate each catalog's license, and host
   the chosen star/culture data under an explicit asset policy.
3. Add a viewer adapter that converts the canonical UTC instant to the viewer's
   MJD interface and converts observer degrees to radians exactly once. Keep these
   presentation conversions outside the Python calculation engine.
4. Freeze viewer time, select the requested physical object, and test the same
   place/time in both engines with an explicitly defined coordinate frame,
   refraction setting, time scale, and numerical tolerance.
5. Retain progressive loading, an accessible textual alternative, and a mobile
   performance budget. Do not load private profile responses into a shared cache.

Stellarium necessarily calculates its own rendered sky internally. "No duplicate
logic" means those calculations are not used to score, validate, or overwrite the
Wealth Algorithm's canonical chart, not that the renderer contains no ephemerides.

## Optional local MCP

Install the project's MCP extra and run `python -m wealth_command_center.mcp_server`
from the application checkout. This adapter targets the maintained SDK v1 line;
the [official SDK](https://github.com/modelcontextprotocol/python-sdk) now also has
a v2 API, so keep the declared `<2` bound until performing an explicit migration.
Use stdio with a trusted local MCP host. The `calculate_profile` tool takes explicit
birth inputs and a mandatory report date, calls the same engine, and saves nothing.
It cannot list accounts, read saved profiles, access journals, or control Stellarium.
The MCP host may retain supplied personal data according to its own policy. No
public network MCP endpoint is created by this module.

Verified with SDK 1.30.0 on 2026-09-26: a real isolated stdio subprocess completed
initialization, `tools/list`, the capabilities resource, and `tools/call` with a
synthetic profile. The call returned structured report data from the Swiss
Ephemeris engine without corrupting the protocol stream. A requested tropical
mode (`sidereal=false`) returned a tool error rather than silently computing a
different framework. This regression check skips only when the optional SDK is
not installed; the ordinary engine tests do not depend on the SDK.

## CosmicCard contract

`cosmic_cards.py` defines `CanonicalEntity`, `ChartPlacement`, `CosmicCard`,
`VisualSpec`, and `Provenance` as versioned Pydantic schemas. `resolve_card` looks
up physical bodies through one registry and consumes chart positions and gates
already present in the canonical report. The Sun-Spirit reference template adds
editorial Fire/Gold and sovereignty/vitality/illumination motifs, explicitly
attributed to the design discussion. These do not affect scores or imply that
the mappings are universal. A personal example's Gate 49 or card rank is never
used as a default. The source report must contain matching longitude evidence;
missing or inconsistent placement is represented as unknown.

The renderer produces a self-contained accessible SVG, with a geometric sun/orbit
motif, finished text layout, and localized labels in all six languages. It embeds
no profile name, birth date, external font/image, script, or account identifier.
The accompanying JSON retains provenance, schema/registry/template versions,
known facts and unresolved correspondences. A SHA-256 fingerprint covers the
resolved data, language, engine provenance and template versions; generation
timestamps and private profile metadata are excluded. Native fonts vary by device;
multilingual typography should still be reviewed by native speakers before release.

Custom stellar-extent Nakshatra boundaries, totems, and body-specific Tarot/card
ranks remain `null` with warnings until their explicit definitions and source
registries are available. The implementation does not substitute equal-width
traditional Nakshatras or manufacture correspondences. More elaborate generated
art is optional future work and is not required for deterministic card facts.

## Release boundary

Desktop Stellarium, the Web Engine, Swiss Ephemeris and its Python binding have
different licenses and distribution obligations. Review them together with the
upstream Wealth Algorithm's missing license before public redistribution. This
local implementation neither assigns an open-source license to the user's work
nor assumes that a commercial Swiss Ephemeris license covers its Python binding.
