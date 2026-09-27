# Wealth Algorithm Agent

Wraps `wealth_algorithm.py` + `cosmic_calendar.py` -- layered with a
64-Gate Human Design system, an Enneagram + MBTI typology overlay, a
Mayan Tzolkin calendar, a 15-cipher numerology ring, a Cosmic Playing
Card + Tarot system, and astrocartography with both static and now
interactive map rendering -- in an Anthropic API tool-calling loop.

## What's new: the interactive map

`tools/astrocartography_interactive.py` + a new
`render_interactive_astrocartography_map` tool. Same line data as the
static renderer, but output is a single self-contained HTML file with
real pan/zoom, a layer-control panel to show/hide individual planets,
and hover tooltips naming each line. `main.py --direct --render-map`
picks the renderer automatically from the file extension you give it
(`.html` -> interactive, `.png`/`.svg` -> static).

## The limitation from last time got resolved, not worked around

The static-image version explained a real constraint: this project's
sandbox can reach GitHub and package registries but not arbitrary CDNs
or map tile servers, so an HTML/JS map couldn't be rendered or
screenshotted to confirm it actually worked before shipping it -- only
reasoned about against documentation. That's what changed here: getting
a headless browser (Playwright's Chromium) working turned out to be
possible in this sandbox, confirmed by actually launching it before
writing any of the map-generation code around it. Every claim below
about this feature working was checked by opening the real generated
file, not assumed from the code looking right.

## Fully self-contained, and why that's a requirement, not a preference

Every generated HTML file embeds Leaflet's JS/CSS and the world boundary
GeoJSON directly inline -- nothing loads from a separate file or a CDN.
This was tested directly rather than assumed: a plain `fetch()` of even
a sibling file in the same folder fails under the `file://` protocol
(confirmed in this project's own sandbox before writing the real
generator). Since double-clicking an HTML file is exactly how this will
actually be opened, a version that reached out to separate `.js`/`.css`/
`.json` files alongside the HTML would have silently failed to load its
own map data the moment anyone actually used it. Leaflet itself is
self-hosted too (`npm install leaflet`, copied into `data/leaflet/`),
not CDN-loaded -- partly for the same reason, partly because self-hosting
is what made verification possible at all in a sandbox that can't reach
arbitrary CDNs.

## What was actually checked, not just coded

  browser and captured console/page errors -- none.
  8 of 10 planet checkboxes off, re-screenshotted, and confirmed only the
  2 remaining planets' lines were still visible. This is the feature that
  justifies building an interactive version at all (40 overlapping lines
  don't declutter with a fixed legend), so it's the one most worth having
  actually clicked rather than assumed.
  and confirmed a tooltip appeared with the correct label ("Mercury DC").
  generated a map by calling the tool through `WealthAgent._dispatch()`
  the same way the real agent loop would, then rendered and screenshotted
  *that* file specifically -- confirming the tool wiring itself produces
  a working file, not just the underlying render function in isolation.
  degrees latitude; Web Mercator (which this map uses, like every
  standard web map) is unusable much past ~85 degrees. Checked by
  rendering rather than assumed away -- the map handles it the same way
  Google Maps or any other Mercator-based map does with high-latitude
  content, not a bug specific to this project.

## Tool list (17 total)

| Tool | Purpose |
| --- | --- |
| `render_interactive_astrocartography_map` | Saves a self-contained interactive HTML map; returns the file path |

`render_astrocartography_map` (static PNG/SVG) and `get_astrocartography_lines`
(raw coordinate data) are both unchanged and still available.

## Structure

```text
wealth_agent/
  tools/
    astrocartography_interactive.py   # new: Leaflet-based interactive HTML renderer
    astrocartography.py                 # +split_on_wraparound moved here (shared by both renderers)
    astrocartography_map.py               # unchanged behavior, now imports the shared helper
  data/
    leaflet/                                # new: self-hosted Leaflet 1.9.4 (JS, CSS, marker images)
  agent_loop.py                             # +1 tool, extended system-prompt guidance
  main.py                                     # --render-map now picks the renderer by file extension

```
