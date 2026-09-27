"""
astrocartography_map.py — render astrocartography lines as an actual map.

Self-contained image output (PNG/SVG via matplotlib), not an HTML/JS
map. That was a deliberate choice, not the default option: an HTML file
with an embedded interactive map (e.g. Leaflet + OpenStreetMap tiles)
would need internet access at VIEW time to load the mapping library and
tiles, and this project has no way to actually render/screenshot that
kind of output to confirm it looks right before shipping it. This
module's output, by contrast, could be (and was) fully rendered and
visually checked the same way the astro.com comparison in
tools/astrocartography.py's docstring was -- see the test run in chat.
If an interactive HTML map is wanted later, it's a separate, addable
capability, not a replacement for this one.

World outline: Natural Earth's public-domain 110m country boundaries
(the standard, widely-used dataset for exactly this kind of small-scale
world map), fetched from the project's own GitHub mirror
(nvkelso/natural-earth-vector) and bundled at data/world_boundaries.json
with coordinates rounded to 2 decimal places (~1km precision -- ample for
a world-scale thumbnail, and it shrinks the bundled file from ~840KB to
~170KB). No network access needed at render time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # no display needed -- this writes files, doesn't pop up a window
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

from .astrocartography import BodyLines

WORLD_BOUNDARIES_PATH = Path(__file__).resolve().parent.parent / "data" / "world_boundaries.json"

# Consistent per-body colors, chosen to stay distinguishable at 10 lines
# on one map (loosely following common ACG software conventions, not
# copying any specific tool's exact palette).
BODY_COLORS: Dict[str, str] = {
    "Sun": "#E8A33D", "Moon": "#4A4A4A", "Mercury": "#8E8E8E",
    "Venus": "#2E8B57", "Mars": "#C0392B", "Jupiter": "#C2185B",
    "Saturn": "#7B241C", "Uranus": "#2E9DD6", "Neptune": "#6A3D9A",
    "Pluto": "#8B5A2B",
}


def _load_world_outline() -> list:
    with open(WORLD_BOUNDARIES_PATH, encoding="utf-8") as f:
        return json.load(f)["features"]


def _split_on_wraparound(points: List[Tuple[float, float]]) -> List[List[Tuple[float, float]]]:
    """An AC/DC curve is generated latitude-by-latitude; where it crosses
    the +-180deg seam, consecutive longitude values jump by ~360deg. A
    naive plot would draw a spurious line straight across the map at that
    point -- split into separate segments there instead."""
    if not points:
        return []
    segments, current = [], [points[0]]
    for prev, curr in zip(points, points[1:]):
        if abs(curr[0] - prev[0]) > 180:
            segments.append(current)
            current = [curr]
        else:
            current.append(curr)
    segments.append(current)
    return segments


def render_map(
    lines: Dict[str, BodyLines],
    output_path: str,
    title: Optional[str] = None,
    bodies: Optional[List[str]] = None,
    dpi: int = 130,
) -> str:
    """Render astrocartography lines onto a world outline and save to
    output_path (format inferred from extension -- .png or .svg).
    Returns output_path. Equirectangular (plain longitude/latitude) axes,
    matching the projection astro.com's own World Map export uses."""
    fig, ax = plt.subplots(figsize=(16, 9))

    # World outline -- light fill, subtle border, deliberately understated
    # so 10 planets' worth of colored lines stay the visual focus.
    patches = []
    for feature in _load_world_outline():
        geom = feature["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            ring = poly[0]  # outer ring only -- islands' small holes aren't worth the complexity here
            patches.append(Polygon(ring, closed=True))
    ax.add_collection(PatchCollection(
        patches, facecolor="#E8E3D8", edgecolor="#A8A296", linewidth=0.4, zorder=1,
    ))

    body_names = bodies if bodies else list(lines.keys())
    for name in body_names:
        if name not in lines:
            continue
        bl = lines[name]
        color = BODY_COLORS.get(name, "#333333")

        ax.axvline(bl.mc_longitude, color=color, linewidth=1.3, zorder=2, label=name)
        ax.axvline(bl.ic_longitude, color=color, linewidth=1.3, zorder=2, linestyle="--")

        for seg in _split_on_wraparound(bl.ac_curve):
            if len(seg) > 1:
                ax.plot([p[0] for p in seg], [p[1] for p in seg], color=color, linewidth=1.5, zorder=2)
        for seg in _split_on_wraparound(bl.dc_curve):
            if len(seg) > 1:
                ax.plot([p[0] for p in seg], [p[1] for p in seg], color=color, linewidth=1.5,
                        linestyle=":", zorder=2)

    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title or "Astrocartography (solid=MC/AC, dashed=IC, dotted=DC)")
    ax.grid(alpha=0.25, zorder=0)
    ax.legend(loc="upper left", fontsize=8, ncol=2, framealpha=0.9)
    plt.tight_layout()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return output_path
