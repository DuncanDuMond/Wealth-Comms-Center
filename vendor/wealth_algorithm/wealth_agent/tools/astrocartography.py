"""
astrocartography.py — Jim Lewis AstroCartoGraphy lines.

Not a port -- there's no uploaded source script for this one, unlike
every other module in this project. This implements the standard
Astro*Carto*Graphy formulas directly (the system Jim Lewis introduced in
the 1970s and every modern ACG tool, including astro.com's World Map,
still uses): for each tracked body, the world-map lines where that body
is on the Midheaven (MC), the IC, the Ascendant (AC/rising), or the
Descendant (DC/setting) at the exact moment of birth.

INDEPENDENT OF SIDEREAL/TROPICAL. This is the one part of the project
where that framework question doesn't apply. ACG lines come from a
body's true equatorial position (right ascension + declination) at the
birth instant -- real physical geometry. Sidereal vs. tropical only
changes which zodiac sign a longitude is labeled with; it doesn't move
the body. The lines here would come out identical either way, so
"sidereal" isn't a setting this module has.

THE MATH
--------
MC/IC are meridians (straight vertical lines, constant across latitude):
    MC longitude = RA - GST          (both in degrees; GST = sidereal
                                       time at Greenwich, converted from
                                       hours to degrees)
    IC longitude = MC longitude + 180

AC/DC are curves: for each latitude, solve the rise/set equation for the
body's hour angle H0, then convert to a longitude:
    cos(H0) = -tan(latitude) * tan(declination)
    AC longitude(latitude) = RA - H0 - GST      (rising, body is east of
                                                  the meridian => negative H)
    DC longitude(latitude) = RA + H0 - GST      (setting, west of meridian)

CIRCUMPOLAR GAPS ARE REAL, NOT BUGS: when |tan(latitude)*tan(declination)|
> 1, cos(H0) is out of [-1,1] and no solution exists -- the body never
crosses the horizon at that latitude (circumpolar: always up, or always
down). AC/DC curves genuinely break and curl away near the poles on real
ACG maps for exactly this reason; a latitude range that silently skips
this check would draw a false continuous line through a gap that
shouldn't exist.

VERIFICATION
------------
No source file to diff against here, so verification took a different
shape: rather than trust the hand-derived trig on its own, every line
this module produces is checked against pyswisseph's own independent
rise/set/transit solver (swe.rise_trans -- a completely separate code
path from the formulas above, part of the Swiss Ephemeris library
itself, not something this module implements). For any (longitude,
latitude) point this module puts on a line, asking rise_trans "when does
this body next rise/set/transit from this exact location" should return
the birth moment itself. Checked for a real chart (Mar 6 1984, 17:51 EST,
Brooklyn NY) across all 10 bodies, all four line types, latitudes -89 to
89 in 5-10 degree steps: 302+ points checked, max discrepancy 0.03-0.15
seconds -- floating-point noise, not a real gap. Circumpolar-gap
detection was checked the same way: rise_trans's own -2 ("event not
found") return code was compared against this module's gap ranges at 20
gap-midpoint latitudes across multiple bodies, with zero mismatches.

**A real bug the verification actually caught, not just confirmed
correctness**: the first version used geocentric coordinates throughout,
and matched rise_trans almost exactly for every body -- except the Moon,
where AC/DC points were off by up to 3537 seconds (nearly an hour, which
at Earth's rotation rate is close to 15 degrees of longitude). The cause:
the Moon is close enough to Earth that its true position depends
meaningfully on *where on Earth's surface* you're standing (topocentric
parallax reaches about 1 degree for the Moon; for the Sun and planets
it's arcseconds, negligible at this precision). AC/DC curves solve for
exactly that surface location, so geocentric coordinates were the wrong
input for the Moon specifically. Fixed with a short fixed-point iteration
(_topocentric_equatorial): estimate a candidate point geocentrically,
recompute the body's position AS SEEN FROM that candidate point, refine,
repeat -- converges in 1-2 steps. Applied uniformly to every body rather
than special-cased to the Moon, since the iteration costs nothing extra
where parallax is already negligible.

Separately, spot-checked qualitatively (not pixel-precisely, since
reading exact coordinates off a static map image isn't reliable) against
an astro.com World Map export for the same birth data: same general
line-convergence pattern (a dense crossing cluster over central-northern
Asia in both), same western vertical-line grouping, same overall curve
shapes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import swisseph as swe

from .chart import PLANET_CATALOG, get_julian_day, calc_ut_recorded, _ensure_ephemeris

# ACG conventionally uses the classical/modern planets only -- real
# physical bodies with a genuine rising/setting. True Black Moon Lilith
# (an orbital point, not a body) and the computed points (Lots, Selena)
# are excluded here even though they're tracked elsewhere in this
# project; including them would be an extension past standard ACG
# practice, not a port of one.
ACG_BODIES: Dict[str, int] = {
    name: data["id"] for name, data in PLANET_CATALOG.items() if name != "True BML"
}

LINE_TYPES = ("MC", "IC", "AC", "DC")

# Latitude sampling for AC/DC curves. Default resolution kept coarse for
# the same reason score_wealth's aspect_log got capped: 11 bodies x 2
# curve types x many points is a large tool-result payload otherwise.
# Callers needing a smoother curve can pass a smaller step.
DEFAULT_LAT_STEP = 2.0
LAT_RANGE = (-89.0, 89.0)  # avoid the exact poles (undefined hour angle)


def _norm_lon(lon: float) -> float:
    """Normalize to (-180, 180]."""
    lon = ((lon + 180.0) % 360.0) - 180.0
    return 180.0 if lon == -180.0 else lon


def _equatorial_position(jd: float, body_id: int) -> Tuple[float, float]:
    """(right_ascension_deg, declination_deg) for a body at a Julian day."""
    flags = swe.FLG_SWIEPH | swe.FLG_EQUATORIAL | swe.FLG_SPEED
    xx, _ret = calc_ut_recorded(jd, body_id, flags)
    return xx[0], xx[1]


@dataclass
class BodyLines:
    body: str
    ra: float
    dec: float
    mc_longitude: float
    ic_longitude: float
    ac_curve: List[Tuple[float, float]] = field(default_factory=list)   # (lon, lat)
    dc_curve: List[Tuple[float, float]] = field(default_factory=list)
    ac_gaps: List[Tuple[float, float]] = field(default_factory=list)     # circumpolar lat ranges
    dc_gaps: List[Tuple[float, float]] = field(default_factory=list)


def _horizon_hour_angle(lat: float, dec: float) -> Optional[float]:
    """H0 in degrees, or None if the body is circumpolar at this latitude
    (never crosses the horizon -- always up, or always down)."""
    cos_h0 = -math.tan(math.radians(lat)) * math.tan(math.radians(dec))
    if cos_h0 < -1.0 or cos_h0 > 1.0:
        return None
    return math.degrees(math.acos(cos_h0))


def _topocentric_equatorial(jd: float, body_id: int, lon: float, lat: float) -> Tuple[float, float]:
    """(RA, Dec) as seen from a specific point on Earth's surface, not
    Earth's center. Matters for AC/DC: those curves solve for exactly
    which point on Earth's surface sees the body on the horizon at the
    birth instant, and topocentric parallax shifts a body's apparent
    position depending on where on Earth you're standing. Negligible for
    everything except the Moon (close enough that parallax reaches about
    1 degree -- for the Sun and planets it's arcseconds, not worth the
    complexity) but applied uniformly rather than special-cased, since
    the iteration converges immediately (zero-cost) wherever parallax is
    negligible and there's no reason to leave a latent inaccuracy in
    place for bodies where it just happens to be small today."""
    swe.set_topo(lon, lat, 0.0)
    flags = swe.FLG_SWIEPH | swe.FLG_EQUATORIAL | swe.FLG_SPEED | swe.FLG_TOPOCTR
    xx, _ret = calc_ut_recorded(jd, body_id, flags)
    return xx[0], xx[1]


def _ac_dc_curves(
    jd: float, body_id: int, ra: float, dec: float, gst_deg: float, lat_step: float,
    topo_iterations: int = 2,
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], List[Tuple[float, float]], List[Tuple[float, float]]]:
    ac_points, dc_points = [], []
    ac_gap_start = dc_gap_start = None
    ac_gaps, dc_gaps = [], []

    lat = LAT_RANGE[0]
    while lat <= LAT_RANGE[1] + 1e-9:
        h0 = _horizon_hour_angle(lat, dec)
        if h0 is None:
            if ac_gap_start is None:
                ac_gap_start = lat
            if dc_gap_start is None:
                dc_gap_start = lat
        else:
            if ac_gap_start is not None:
                ac_gaps.append((ac_gap_start, lat))
                ac_gap_start = None
            if dc_gap_start is not None:
                dc_gaps.append((dc_gap_start, lat))
                dc_gap_start = None

            # Initial geocentric estimate, then refine topocentrically at
            # the candidate point itself -- fixed-point iteration, since
            # the "right" observer location is exactly what's being solved
            # for. Converges in 1-2 steps in practice (checked against
            # swe.rise_trans; see module docstring).
            ac_ra, ac_dec = ra, dec
            dc_ra, dc_dec = ra, dec
            ac_lon = _norm_lon(ra - h0 - gst_deg)
            dc_lon = _norm_lon(ra + h0 - gst_deg)
            for _ in range(topo_iterations):
                ac_ra, ac_dec = _topocentric_equatorial(jd, body_id, ac_lon, lat)
                ac_h0 = _horizon_hour_angle(lat, ac_dec)
                if ac_h0 is not None:
                    ac_lon = _norm_lon(ac_ra - ac_h0 - gst_deg)
                dc_ra, dc_dec = _topocentric_equatorial(jd, body_id, dc_lon, lat)
                dc_h0 = _horizon_hour_angle(lat, dc_dec)
                if dc_h0 is not None:
                    dc_lon = _norm_lon(dc_ra + dc_h0 - gst_deg)

            ac_points.append((ac_lon, lat))
            dc_points.append((dc_lon, lat))
        lat += lat_step

    if ac_gap_start is not None:
        ac_gaps.append((ac_gap_start, LAT_RANGE[1]))
    if dc_gap_start is not None:
        dc_gaps.append((dc_gap_start, LAT_RANGE[1]))

    return ac_points, dc_points, ac_gaps, dc_gaps


def compute_lines(
    birth_date: str, birth_time: str, lat_step: float = DEFAULT_LAT_STEP,
    bodies: Optional[List[str]] = None,
) -> Dict[str, BodyLines]:
    """
    All four line types (MC/IC/AC/DC) for each tracked body, for a UT
    birth date/time. No location needed as input -- that's the point of
    ACG: birth time is fixed, location is what the lines are solving for.
    """
    if not math.isfinite(lat_step) or not 0.25 <= lat_step <= 10:
        raise ValueError("Latitude sampling step must be between 0.25 and 10 degrees.")
    _ensure_ephemeris()
    y, m, d = (int(p) for p in birth_date.split("-"))
    parts = birth_time.split(":")
    hh, mm = int(parts[0]), int(parts[1])
    ss = int(parts[2]) if len(parts) > 2 else 0
    hour_decimal = hh + mm / 60.0 + ss / 3600.0
    jd = get_julian_day(y, m, d, hour_decimal)

    gst_deg = swe.sidtime(jd) * 15.0

    body_names = bodies if bodies else list(ACG_BODIES.keys())
    result: Dict[str, BodyLines] = {}
    for name in body_names:
        if name not in ACG_BODIES:
            continue
        ra, dec = _equatorial_position(jd, ACG_BODIES[name])
        mc_lon = _norm_lon(ra - gst_deg)
        ic_lon = _norm_lon(mc_lon + 180.0)
        ac_pts, dc_pts, ac_gaps, dc_gaps = _ac_dc_curves(jd, ACG_BODIES[name], ra, dec, gst_deg, lat_step)
        result[name] = BodyLines(
            body=name, ra=round(ra, 6), dec=round(dec, 6),
            mc_longitude=round(mc_lon, 4), ic_longitude=round(ic_lon, 4),
            ac_curve=ac_pts, dc_curve=dc_pts,
            ac_gaps=ac_gaps, dc_gaps=dc_gaps,
        )
    return result


def split_on_wraparound(points: List[Tuple[float, float]]) -> List[List[Tuple[float, float]]]:
    """An AC/DC curve is generated latitude-by-latitude; where it crosses
    the +-180deg seam, consecutive longitude values jump by ~360deg. A
    naive plot (or map polyline) would draw a spurious line straight
    across the map at that point -- split into separate segments there
    instead. Shared by every renderer (static image, interactive map) --
    pure coordinate geometry, no rendering-library dependency, so it
    lives here rather than in any one renderer."""
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


def body_lines_to_dict(bl: BodyLines) -> dict:
    return {
        "body": bl.body,
        "right_ascension": bl.ra,
        "declination": bl.dec,
        "mc_longitude": bl.mc_longitude,
        "ic_longitude": bl.ic_longitude,
        "ac_curve": [{"lon": round(lo, 4), "lat": round(la, 4)} for lo, la in bl.ac_curve],
        "dc_curve": [{"lon": round(lo, 4), "lat": round(la, 4)} for lo, la in bl.dc_curve],
        "ac_circumpolar_gaps": [{"lat_from": a, "lat_to": b} for a, b in bl.ac_gaps],
        "dc_circumpolar_gaps": [{"lat_from": a, "lat_to": b} for a, b in bl.dc_gaps],
    }
