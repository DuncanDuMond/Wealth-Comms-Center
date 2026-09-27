"""
astrocartography_interactive.py — interactive HTML/Leaflet version of the
astrocartography map.

FULLY SELF-CONTAINED, SINGLE FILE, BY REQUIREMENT NOT PREFERENCE: every
generated HTML file embeds Leaflet's JS/CSS and the world boundary
GeoJSON directly as inline <style>/<script> content -- nothing is loaded
from a separate file or a CDN. This was verified to be necessary, not
just a nice-to-have: opening an HTML file via the file:// protocol (i.e.
someone double-clicking it, which is how this will actually be viewed)
blocks fetch() of even a sibling file in the same folder as a CORS
violation. Confirmed directly in this project's own sandbox before
building around it -- see the test run in chat. A version that reached
out to separate .js/.css/.json files alongside the HTML would silently
fail to load its own map data the moment someone actually opened it.

Leaflet is self-hosted (installed via `npm install leaflet`, copied into
data/leaflet/), not CDN-loaded, for the same reason plus one more: this
project's sandbox can reach npm's registry but not arbitrary CDNs, so
self-hosting was also what made it possible to verify this at all (see
below).

PROJECTION: standard Leaflet/Web Mercator (the same projection every
familiar web map uses), not a flat equirectangular plot -- no tile
server is used (nothing here needs live imagery), but the world
boundaries are rendered as a vector GeoJSON layer using the same bundled
data/world_boundaries.json as the static renderer, styled to look like
a basic map rather than left as plain outlines. Web Mercator distorts
heavily near the poles (unusable much past ~85 degrees latitude, a
property of the projection itself, not a bug) -- AC/DC curves in this
project extend to +-89 degrees, so the extreme ends of some curves will
visually run off-screen or compress oddly near the poles, matching how
every standard web map (including Google Maps) handles the same
latitudes. Checked directly by rendering and screenshotting, not assumed.

VERIFICATION: this project's sandbox has network access to npm's
registry and GitHub, not arbitrary CDNs or tile servers -- which was the
reason a static image was built first rather than this. Getting a
headless-browser check working here changed that: Playwright's Chromium
downloads through a path this sandbox could actually reach, confirmed by
launching it and rendering+screenshotting real interactive JS output
before writing this module's generation logic around it. Every generated
map from this module can therefore be, and was, actually opened
(file://), rendered, and screenshotted for a real visual check -- not
just reasoned about against Leaflet's documented API. See the test run
in chat for what was checked: the full 10-body render, a filtered subset,
and the layer-control checkboxes toggling lines on/off.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .astrocartography import BodyLines, split_on_wraparound
from .astrocartography_map import BODY_COLORS, WORLD_BOUNDARIES_PATH

LEAFLET_DIR = Path(__file__).resolve().parent.parent / "data" / "leaflet"
LEAFLET_JS_PATH = LEAFLET_DIR / "leaflet.js"
LEAFLET_CSS_PATH = LEAFLET_DIR / "leaflet.css"
# Leaflet's CSS references these by relative "images/..." url() -- inlined
# as base64 data URIs into the CSS text at generation time so the CSS
# itself never needs a separate file lookup either.
LEAFLET_IMAGES_DIR = LEAFLET_DIR / "images"


def _inline_leaflet_css_images(css_text: str) -> str:
    import base64
    for img_path in LEAFLET_IMAGES_DIR.glob("*.png"):
        b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
        css_text = css_text.replace(
            f"images/{img_path.name}", f"data:image/png;base64,{b64}"
        )
    return css_text


def _body_lines_js_data(lines: Dict[str, BodyLines], bodies: Optional[List[str]]) -> dict:
    """{body: {mc, ic, ac_segments, dc_segments}} -- Leaflet wants
    [lat, lng] point order, the opposite of this project's (lon, lat)
    convention used everywhere else, so the flip happens once here."""
    body_names = bodies if bodies else list(lines.keys())
    out = {}
    for name in body_names:
        if name not in lines:
            continue
        bl = lines[name]
        out[name] = {
            "mc": bl.mc_longitude,
            "ic": bl.ic_longitude,
            "ac_segments": [[[lat, lon] for lon, lat in seg] for seg in split_on_wraparound(bl.ac_curve)],
            "dc_segments": [[[lat, lon] for lon, lat in seg] for seg in split_on_wraparound(bl.dc_curve)],
            "color": BODY_COLORS.get(name, "#333333"),
        }
    return out


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; }
  #map { width: 100%; height: 100%; background: #AFC9E0; }
  .acg-legend-swatch { display: inline-block; width: 14px; height: 3px; margin-right: 6px; vertical-align: middle; }
__LEAFLET_CSS__
</style>
</head>
<body>
<div id="map"></div>
<script>
__LEAFLET_JS__
</script>
<script>
var worldBoundaries = __WORLD_GEOJSON__;
var bodyLines = __BODY_LINES__;

var map = L.map('map', { worldCopyJump: true }).setView([20, 0], 2);

L.geoJSON(worldBoundaries, {
  style: { color: '#A8A296', weight: 0.6, fillColor: '#E8E3D8', fillOpacity: 1 }
}).addTo(map);

var overlays = {};
for (var body in bodyLines) {
  var d = bodyLines[body];
  var group = L.layerGroup();

  var mcLine = L.polyline([[-85, d.mc], [85, d.mc]], { color: d.color, weight: 2 })
    .bindTooltip(body + ' MC');
  var icLine = L.polyline([[-85, d.ic], [85, d.ic]], { color: d.color, weight: 2, dashArray: '6,5' })
    .bindTooltip(body + ' IC');
  mcLine.addTo(group);
  icLine.addTo(group);

  d.ac_segments.forEach(function(seg) {
    if (seg.length > 1) {
      L.polyline(seg, { color: d.color, weight: 2 }).bindTooltip(body + ' AC').addTo(group);
    }
  });
  d.dc_segments.forEach(function(seg) {
    if (seg.length > 1) {
      L.polyline(seg, { color: d.color, weight: 2, dashArray: '2,5' }).bindTooltip(body + ' DC').addTo(group);
    }
  });

  group.addTo(map);
  var swatch = '<span class="acg-legend-swatch" style="background:' + d.color + '"></span>' + body;
  overlays[swatch] = group;
}

L.control.layers(null, overlays, { collapsed: false }).addTo(map);
</script>
</body>
</html>
"""


def render_interactive_map(
    lines: Dict[str, BodyLines],
    output_path: str,
    title: Optional[str] = None,
    bodies: Optional[List[str]] = None,
) -> str:
    """Render astrocartography lines as a single self-contained
    interactive HTML file (pan/zoom, per-planet show/hide via the layer
    control, hover tooltips naming each line) and save to output_path.
    Returns output_path. Opens directly via file:// -- no server, no
    network access, no separate files needed."""
    leaflet_js = LEAFLET_JS_PATH.read_text(encoding="utf-8")
    leaflet_css = _inline_leaflet_css_images(LEAFLET_CSS_PATH.read_text(encoding="utf-8"))
    world_geojson = json.loads(WORLD_BOUNDARIES_PATH.read_text(encoding="utf-8"))
    body_lines_data = _body_lines_js_data(lines, bodies)

    html = (
        _HTML_TEMPLATE
        .replace("__TITLE__", title or "Astrocartography")
        .replace("__LEAFLET_CSS__", leaflet_css)
        .replace("__LEAFLET_JS__", leaflet_js)
        .replace("__WORLD_GEOJSON__", json.dumps(world_geojson, separators=(",", ":")))
        .replace("__BODY_LINES__", json.dumps(body_lines_data))
    )

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)

