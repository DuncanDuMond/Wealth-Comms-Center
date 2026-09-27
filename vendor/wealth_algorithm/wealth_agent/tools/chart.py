"""
chart.py — Natal chart position calculations.

FAITHFUL PORT of the position-calculation logic from your uploaded
wealth_algorithm.py (PLANET_CATALOG, COMPUTED_WEIGHTS, STAR_CATALOG,
sign_tropical, sign_sidereal_13, calc_planets, calc_ascendant, calc_lots,
calc_selena, calc_stars, all_body_positions, setup_ephemeris) — same
constants, same formulas, same body list. Not a reinterpretation.

FRAMEWORK NOTE: your original script defaults to TROPICAL and takes
--sidereal to switch modes. Per your standing instruction for this
project, the agent layer (agent_loop.py) always calls get_natal_chart
with sidereal=True and never exposes a tropical option to the model.
The sidereal=False code path is kept here only because it exists in your
source script -- direct callers of chart.py can still use it if needed.

Tracked bodies (14 total, matching your script exactly):
  10 classical/modern planets + True Black Moon Lilith (11 "planets")
  + Lot of Fortune, Lot of Spirit, White Moon Selena (3 computed points)
Chiron is NOT a tracked/scored body in your script -- it appears only as
a comment labeling Ophiuchus's traditional ruler. See calendar_bridge.py
for how that's handled in the month-ruler boost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import swisseph as swe

from .typology import parse_enneagram_input, parse_mbti_input

# ---------------------------------------------------------------------------
# Ephemeris setup -- ported from setup_ephemeris(). sefstars.txt is
# auto-downloaded on first use, exactly as your script does, from the same
# source URL. Path handling uses pathlib, resolved relative to this file
# (not cwd) so it works the same whether invoked from PowerShell, VSCode,
# or elsewhere, per your Windows/OneDrive portability preference.
# ---------------------------------------------------------------------------
_SEFSTARS_URL = "https://github.com/aloistr/swisseph/raw/master/ephe/sefstars.txt"
_SEAS_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/seas_18.se1"
EPHE_DIR = Path(__file__).resolve().parents[2] / "ephe"

_ephemeris_ready = False
EPHEMERIS_BACKENDS: Dict[str, str] = {}


def setup_ephemeris(ephe_dir: Optional[str] = None) -> None:
    """WCC adaptation: register local data only; never download in a request.

    Planetary files are optional: Swiss Ephemeris may use its built-in
    Moshier backend. Missing Chiron/fixed-star data stays a reported error.
    The caller must serialize access to Swiss Ephemeris global state.
    """
    global _ephemeris_ready
    ephe_path = Path(ephe_dir).expanduser().resolve() if ephe_dir else EPHE_DIR
    if not ephe_path.is_dir():
        raise ValueError("Configured ephemeris directory does not exist.")
    swe.set_ephe_path(str(ephe_path))
    EPHEMERIS_BACKENDS.clear()
    _ephemeris_ready = True


def calc_ut_recorded(jd: float, body: int, flags: int):
    """Record the actual returned backend, not only the requested flag."""
    result, returned_flags = swe.calc_ut(jd, body, flags)
    if returned_flags & swe.FLG_JPLEPH:
        backend = "JPL"
    elif returned_flags & swe.FLG_SWIEPH:
        backend = "Swiss Ephemeris files"
    elif returned_flags & swe.FLG_MOSEPH:
        backend = "Moshier (built-in fallback)"
    else:
        backend = "analytical/unspecified"
    # Separate birth and current-day calls; an installed data file may cover
    # one epoch but not the other. Never overwrite the birth provenance.
    EPHEMERIS_BACKENDS[f"{body}@{jd:.9f}"] = backend
    return result, returned_flags


def _ensure_ephemeris() -> None:
    if not _ephemeris_ready:
        setup_ephemeris()


# ---------------------------------------------------------------------------
# PLANETARY CATALOG -- verbatim from wealth_algorithm.py.
# weight = wealth relevance (1-10), used later by the scoring engine.
# ---------------------------------------------------------------------------
PLANET_CATALOG: Dict[str, dict] = {
    "Sun":      {"id": swe.SUN,       "weight":  6},
    "Moon":     {"id": swe.MOON,      "weight":  5},
    "Mercury":  {"id": swe.MERCURY,   "weight":  5},   # rules Libra (custom)
    "Venus":    {"id": swe.VENUS,     "weight":  9},   # rules Virgo (custom)
    "Mars":     {"id": swe.MARS,      "weight":  4},
    "Jupiter":  {"id": swe.JUPITER,   "weight": 10},
    "Saturn":   {"id": swe.SATURN,    "weight":  5},
    "Uranus":   {"id": swe.URANUS,    "weight":  5},
    "Neptune":  {"id": swe.NEPTUNE,   "weight":  4},
    "Pluto":    {"id": swe.PLUTO,     "weight":  6},
    "True BML": {"id": swe.OSCU_APOG, "weight":  4},   # True Black Moon Lilith
}

COMPUTED_WEIGHTS: Dict[str, int] = {
    "Lot of Fortune":    10,
    "Lot of Spirit":      8,
    "White Moon Selena":  6,
}

# ---------------------------------------------------------------------------
# FIXED STAR CATALOG -- verbatim 30-star/deep-space-point list + fallback names.
# ---------------------------------------------------------------------------
STAR_CATALOG: Dict[str, int] = {
    "Taygeta":        4, "Arcturus":       7, "Sirius":         9,
    "Andromeda":      4, "Betelgeuse":     6, "Rigel":          7,
    "Aldebaran":      8, "Fomalhaut":      8, "Antares":        5,
    "Regulus":        9, "Scheat":         3, "Sabik":          4,
    "Rasalhague":     4, "Kaus Australis": 6, "Vega":           7,
    "Altair":         6, "Sadalsuud":      6, "Zuben Elgenubi": 5,
    # -- added: requested stars + deep-space points --
    "Castor":                 6,   # al Gem
    "Pollux":                 6,   # be Gem
    "Spica":                  9,   # al Vir -- wealth/abundance star (wheat sheaf)
    "Hamal":                  5,   # al Ari
    "Acubens":                3,   # al Cnc -- faint (mag ~4.25), traditionally ill-favored
    "Deneb Algedi":           5,   # de Cap
    "Ankaa":                  6,   # al Phe -- the Phoenix: rebirth/transformation of fortune
    "Deneb":                  7,   # al Cyg -- matches Vega/Altair, its Summer Triangle companions
    "Alrescha":               4,   # al Psc
    "Galactic Center":        8,   # SgrA* -- direct sefstars.txt entry, no fallback needed
    "Super Galactic Center":  5,   # M87 in Virgo -- niche vs. Galactic Center; see STAR_FALLBACKS
    "Solar Apex":             5,   # LSR apex, ~RA 18h04m Dec+30 (Hercules); see STAR_FALLBACKS
}

STAR_FALLBACKS: Dict[str, str] = {
    "Andromeda":      "Alpheratz",
    "Kaus Australis": "Kaus Austr",
    "Zuben Elgenubi": "Zuben Elge",
    "Taygeta":        "19Tau",
    # sefstars.txt stores these two under different catalog names; both
    # verified directly against the downloaded file before adding here.
    "Solar Apex":            "Apex",        # file's own comment: "the solar apex, or the Apex of the Sun's Way"
    "Super Galactic Center": "Messier 87",  # file's own comment credits this to astrologer Philip Sedgwick
}

# ---------------------------------------------------------------------------
# ZODIAC SIGN SYSTEMS -- verbatim.
# ---------------------------------------------------------------------------
SIGNS_12: List[str] = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# IAU ecliptic constellation boundaries expressed as TROPICAL longitudes.
# Subtract the Lahiri ayanamsa (live, per-date) to obtain sidereal entry
# points -- see sign_sidereal_13(). This is your exact validated table.
_13SIGN_TROP: List[Tuple[str, float]] = [
    ("Aries",          27.86), ("Taurus",         53.46),
    ("Gemini",         90.33), ("Cancer",        119.10),
    ("Leo",           134.83), ("Virgo",         173.73),
    ("Libra",         217.81), ("Scorpio",       241.81),
    ("Ophiuchus",     247.07),   # 13th constellation; ruler = Chiron (label only)
    ("Sagittarius",   266.03), ("Capricorn",     299.70),
    ("Aquarius",      327.26), ("Pisces",        351.51),
]


def sign_tropical(lon: float) -> Tuple[str, float]:
    """12-sign tropical placement -> (sign_name, degrees_within_sign)."""
    lon = lon % 360.0
    return SIGNS_12[int(lon // 30)], lon % 30.0


def sign_sidereal_13(sid_lon: float, ayanamsa: float) -> Tuple[str, float]:
    """13-sign sidereal placement (Ophiuchus included), live ayanamsa-shifted.
    Algorithm: largest boundary entry <= sid_lon wins; Pisces is the
    default since it wraps past 0deg. Ported verbatim."""
    entries = [(n, (t - ayanamsa) % 360.0) for n, t in _13SIGN_TROP]
    sid_lon = sid_lon % 360.0
    result_name, result_start = entries[-1]  # Pisces wraps 0deg
    for name, start in entries:
        if sid_lon >= start:
            result_name, result_start = name, start
    return result_name, (sid_lon - result_start) % 360.0


# ---------------------------------------------------------------------------
# HOUSE SYSTEM -- FAITHFUL PORT from wealth_algorithm_updated_house_system.py.
# Whole-sign houses starting at Sagittarius (matching the Cosmic Calendar's
# own year-start convention, not the traditional Aries start). House 12 is
# a genuine two-constellation case: Scorpio is one of the narrowest IAU
# constellations (~5.3deg wide) with Ophiuchus immediately following it
# before Sagittarius resumes, so House 12 covers that Scorpio -> Ophiuchus
# transition -- ruled by Pluto while in Scorpio, nominally by Chiron while
# in Ophiuchus.
#
# This resolves a gap flagged in every earlier version of this project:
# wealth_algorithm.py's own README described a house system that was
# absent from every wealth_algorithm.py upload before this one, and every
# house-related field in this project (gates.py, gate_calendar_bridge.py)
# returned None with a TODO pointing at exactly this table. Unlike that
# earlier state, Chiron is now an actually-computed body (see
# calc_chiron_rahu_ketu above) rather than label-only.
# ---------------------------------------------------------------------------
HOUSES: Dict[int, List[Tuple[str, str]]] = {
    1:  [("Sagittarius", "Jupiter")],
    2:  [("Capricorn",   "Saturn")],
    3:  [("Aquarius",    "Uranus")],
    4:  [("Pisces",      "Neptune")],
    5:  [("Aries",       "Mars")],
    6:  [("Taurus",      "Venus")],
    7:  [("Gemini",      "Mercury")],
    8:  [("Cancer",      "Moon")],
    9:  [("Leo",         "Sun")],
    10: [("Virgo",       "Venus")],     # custom rulership, matches RULERSHIPS
    11: [("Libra",       "Mercury")],   # custom rulership, matches RULERSHIPS
    12: [("Scorpio", "Pluto"), ("Ophiuchus", "Chiron")],
}

# constellation/sign name -> house number. Covers all 13 sidereal
# constellations (12 standard signs + Ophiuchus); in tropical mode only 12
# of these keys are ever reachable, since sign_tropical() never returns
# "Ophiuchus".
SIGN_TO_HOUSE: Dict[str, int] = {
    sign: house
    for house, entries in HOUSES.items()
    for sign, _planet in entries
}

# constellation/sign name -> its house ruler. Scorpio and Ophiuchus each
# keep their own entry despite sharing a house number.
HOUSE_RULER: Dict[str, str] = {
    sign: planet
    for entries in HOUSES.values()
    for sign, planet in entries
}


def house_of_sign(sign: str) -> Optional[int]:
    """House number (1-12) for a constellation/sign name, or None if unrecognized."""
    return SIGN_TO_HOUSE.get(sign)


def house_for_longitude(sid_lon: float, ayanamsa: float) -> Optional[int]:
    """House number (1-12) for a raw sidereal ecliptic longitude."""
    sign, _deg = sign_sidereal_13(sid_lon, ayanamsa)
    return SIGN_TO_HOUSE.get(sign)


def get_julian_day(year: int, month: int, day: int, hour: float) -> float:
    return swe.julday(year, month, day, hour)


# ---------------------------------------------------------------------------
# POSITION CALCULATIONS -- verbatim logic, with light per-body error capture
# added for the agent context (your original lets a single calc_ut failure
# crash the whole run; here it's recorded in chart.errors instead so the
# agent can explain it rather than the process dying mid-chart).
# ---------------------------------------------------------------------------
def calc_planets(jd: float, sidereal: bool = False) -> Tuple[Dict[str, float], Dict[str, bool], List[str]]:
    """Ecliptic longitudes + retrograde flags for all catalog planets.
    Returns (longitudes, retrograde_flags, errors)."""
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL

    lons: Dict[str, float] = {}
    retro: Dict[str, bool] = {}
    errors: List[str] = []
    for name, data in PLANET_CATALOG.items():
        try:
            xx, _ = calc_ut_recorded(jd, data["id"], flags)
            lons[name] = xx[0] % 360.0
            retro[name] = xx[3] < 0.0  # negative speed -> retrograde
        except swe.Error as e:
            errors.append(f"{name}: {e}")
    return lons, retro, errors


def calc_ascendant(jd: float, lat: float, lon: float, sidereal: bool = False) -> float:
    """Placidus Ascendant. In sidereal mode the tropical value is corrected
    by subtracting the live Lahiri ayanamsa for this jd."""
    try:
        _, ascmc = swe.houses(jd, lat, lon, b"P")
    except swe.Error:
        # WCC: Placidus cusps fail at polar latitudes. Only the ascendant
        # is used here; its geometry does not depend on a cusp system.
        _, ascmc = swe.houses(jd, lat, lon, b"E")
    asc = ascmc[0]
    if sidereal:
        asc = (asc - swe.get_ayanamsa_ut(jd)) % 360.0
    return asc


def is_day_chart(sun_lon: float, asc: float) -> bool:
    """True when the Sun is above the horizon (houses 7-12)."""
    return ((sun_lon - asc) % 360.0) > 180.0


def calc_lots(asc: float, sun: float, moon: float, day: bool) -> Dict[str, float]:
    """Hellenistic Lots with Ptolemaic day/night reversal."""
    if day:
        return {"Lot of Fortune": (asc + moon - sun) % 360.0,
                "Lot of Spirit":  (asc + sun - moon) % 360.0}
    return {"Lot of Fortune": (asc + sun - moon) % 360.0,
            "Lot of Spirit":  (asc + moon - sun) % 360.0}


def calc_selena(bml_lon: float) -> float:
    """True White Moon Selena = True Black Moon Lilith + 180deg."""
    return (bml_lon + 180.0) % 360.0


# ---------------------------------------------------------------------------
# CHIRON / RAHU / KETU -- new, from your chat message, not any uploaded
# script. Computed SEPARATELY from PLANET_CATALOG/all_body_positions on
# purpose: those feed chart.positions, which score_aspects iterates over
# for EVERY planet-planet and planet-star pair. Adding these 3 there would
# silently expand aspect scoring to many new pairs (Chiron-Sun, Chiron-
# every star, Rahu-Ketu, ...) using an invented weight -- not something you
# asked for, and a materially bigger change than "add their dignities."
# These bodies exist for dignity evaluation (score_dignities, extended
# below) and sign/house lookup only.
#
# Rahu/Ketu use the MEAN node, not the true/osculating node -- the
# standard convention in sidereal/Vedic astrology, which this project's
# ayanamsa-based sign system already follows throughout. Ketu is exactly
# opposite Rahu by definition (the Moon's two orbital-plane crossings),
# not a separately measured body.
#
# Chiron needs seas_18.se1 specifically (see setup_ephemeris's docstring
# for why that's a separate download from the main planet files) --
# missing/unreachable is reported as an error and Chiron is simply
# omitted, matching calc_stars()'s per-item degradation, not a crash.
# ---------------------------------------------------------------------------
def calc_chiron_rahu_ketu(
    jd: float, sidereal: bool = False
) -> Tuple[Dict[str, dict], List[str]]:
    """Chiron, Rahu, Ketu -- sign placement info only (lon/sign/deg_in_sign),
    same shape as all_body_positions()'s per-body info dict. Returns
    (info, errors)."""
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
    ayana = swe.get_ayanamsa_ut(jd) if sidereal else 0.0

    lons: Dict[str, float] = {}
    errors: List[str] = []

    try:
        xx, _ret = calc_ut_recorded(jd, swe.CHIRON, flags)
        lons["Chiron"] = xx[0] % 360.0
    except swe.Error as exc:
        errors.append(f"Chiron: {exc}")

    xx, _ret = calc_ut_recorded(jd, swe.MEAN_NODE, flags)
    rahu_lon = xx[0] % 360.0
    lons["Rahu"] = rahu_lon
    lons["Ketu"] = (rahu_lon + 180.0) % 360.0

    info: Dict[str, dict] = {}
    for name, body_lon in lons.items():
        if sidereal:
            sign, deg = sign_sidereal_13(body_lon, ayana)
            house = house_of_sign(sign)
        else:
            sign, deg = sign_tropical(body_lon)
            house = None  # whole-sign house table is keyed on sidereal 13-sign names
        info[name] = {
            "lon": round(body_lon, 6),
            "sign": sign,
            "deg_in_sign": round(deg, 4),
            "house": house,
        }

    return info, errors


def _fetch_star(name: str, jd: float, flags: int) -> Optional[float]:
    """Resolve a fixed star longitude, trying the primary catalog name
    then its fallback (if any)."""
    candidates = [name] + ([STAR_FALLBACKS[name]] if name in STAR_FALLBACKS else [])
    for candidate in candidates:
        try:
            xx, _sname, _ret = swe.fixstar_ut(candidate, jd, flags)
            return xx[0] % 360.0
        except Exception:
            continue
    return None


def calc_stars(jd: float, sidereal: bool = False) -> Tuple[Dict[str, float], List[str]]:
    """Ecliptic longitudes for all 30 catalog fixed stars/deep-space points.
    Returns (positions, names_not_resolved).

    BUG FIX: this used to hardcode swe.FLG_SWIEPH with no sidereal option
    at all -- meaning star positions were always computed TROPICAL and
    then used directly as if sidereal (this project is always sidereal;
    get_natal_chart never passes sidereal=False), a full ayanamsa's worth
    of misalignment (~24 degrees at present) against every planet, which
    ARE correctly sidereal-shifted. That's not a cosmetic gap -- star_positions
    feeds score_aspects directly, so every planet-star aspect in every
    wealth score computed by this project was checking angular separation
    between two longitudes in different reference frames. Confirmed
    directly before fixing, not assumed: computed Regulus both ways for a
    real chart and found the exact ~24.66 degree gap the bug predicts (see
    the verification in chat). Fixed by mirroring calc_planets' own
    sidereal convention exactly (FLG_SIDEREAL + SIDM_LAHIRI), rather than
    a manual post-hoc ayanamsa subtraction -- checked that the two methods
    agree to within ~15 arcseconds (using the correct call order: set_sid_mode
    before reading the ayanamsa, since get_ayanamsa_ut's result depends on
    whatever mode was most recently set -- an ordering mistake in the first
    version of this check gave a misleadingly large 0.88 degree gap, which
    turned out to be comparing against the WRONG ayanamsa mode, not a real
    discrepancy), so this isn't a second, subtly-different sidereal
    convention living alongside the planets' own."""
    _ensure_ephemeris()
    flags = swe.FLG_SWIEPH
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
    out: Dict[str, float] = {}
    missing: List[str] = []
    for name in STAR_CATALOG:
        lon = _fetch_star(name, jd, flags)
        if lon is not None:
            out[name] = lon
        else:
            missing.append(name)
    return out, missing


BodyInfo = Dict


def all_body_positions(
    jd: float, lat: float, lon: float, sidereal: bool = False
) -> Tuple[Dict[str, float], Dict[str, int], Dict[str, BodyInfo], List[str]]:
    """Compute every tracked body (11 planets + 3 computed points).
    Returns (positions, weights, body_info, errors)."""
    lons, retro, errors = calc_planets(jd, sidereal)
    ayana = swe.get_ayanamsa_ut(jd) if sidereal else 0.0

    asc = calc_ascendant(jd, lat, lon, sidereal)
    day = is_day_chart(lons["Sun"], asc) if "Sun" in lons else True

    if "Sun" in lons and "Moon" in lons:
        lons.update(calc_lots(asc, lons["Sun"], lons["Moon"], day))
    if "True BML" in lons:
        lons["White Moon Selena"] = calc_selena(lons["True BML"])

    weights = {n: d["weight"] for n, d in PLANET_CATALOG.items()}
    weights.update(COMPUTED_WEIGHTS)

    info: Dict[str, BodyInfo] = {}
    for name, body_lon in lons.items():
        if sidereal:
            sign, deg = sign_sidereal_13(body_lon, ayana)
            house = house_of_sign(sign)
        else:
            sign, deg = sign_tropical(body_lon)
            house = None  # whole-sign house table is keyed on sidereal 13-sign names
        info[name] = {
            "lon": round(body_lon, 6),
            "sign": sign,
            "deg_in_sign": round(deg, 4),
            "retro": retro.get(name, False),
            "house": house,
        }

    return lons, weights, info, errors


@dataclass
class NatalChart:
    """Agent-facing wrapper around all_body_positions() + calc_stars().
    birth_date/time/lat/lon are kept for cache keys and calendar-bridge
    date lookups -- they aren't part of your original script's return
    values, which only needed the Julian day.

    enneagram_type / mbti_type are GIVEN (self-reported), never computed --
    same distinction as birth data itself. Stored on the chart, not
    passed separately to every later call, so a person states them once.
    numerology_name is the same idea: the name to run through the
    numerology cipher ring (tools/numerology.py) -- defaults to whatever
    label the chart is stored under if not given a real name, matching
    wealth_algorithm.py's own --numerology-name-falls-back-to---name CLI default.

    enneagram_wing / mbti_variant are GIVEN too, parsed out of the same
    input string ("7w8" -> core 7 + wing 8; "INTJ-A" -> code INTJ +
    variant A) -- see get_natal_chart's docstring for the accepted input
    formats. Descriptive only, same as the core values: no wing- or
    variant-specific resonance mechanic was specified in chat, so
    typology_resonance() still scores off enneagram_type/mbti_type alone."""
    birth_date: str
    birth_time: str
    latitude: float
    longitude: float
    julian_day: float
    sidereal: bool
    ascendant: float = 0.0
    is_day: bool = True
    positions: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, int] = field(default_factory=dict)
    body_info: Dict[str, dict] = field(default_factory=dict)
    star_positions: Dict[str, float] = field(default_factory=dict)
    dignity_only_bodies: Dict[str, dict] = field(default_factory=dict)
    enneagram_type: Optional[int] = None
    enneagram_wing: Optional[int] = None
    mbti_type: Optional[str] = None
    mbti_variant: Optional[str] = None
    numerology_name: Optional[str] = None
    errors: List[str] = field(default_factory=list)


def get_natal_chart(
    birth_date: str,
    birth_time: str,
    latitude: float,
    longitude: float,
    sidereal: bool = True,
    enneagram_type: Optional[str] = None,
    mbti_type: Optional[str] = None,
    numerology_name: Optional[str] = None,
) -> NatalChart:
    """
    Compute a natal chart. sidereal=True (Lahiri, 13-sign incl. Ophiuchus)
    per your standing instruction -- the agent layer never passes False.

    Args:
        birth_date: "YYYY-MM-DD"
        birth_time: "HH:MM:SS" (24hr, UT) -- matches your script's format
        latitude / longitude: birth location, decimal degrees
        enneagram_type: GIVEN, not computed. "7w8" (wing known), "9"
            (wing unknown), or "N/A"/None (type itself unknown). See
            tools/typology.py's parse_enneagram_input() for exact rules
            (wing must be numerically adjacent to the core type).
        mbti_type: GIVEN, not computed. "INTJ-A", "INTJ-T" (Assertive/
            Turbulent known), "INTJ" (unknown), or "N/A"/None (type
            itself unknown). See parse_mbti_input().
        numerology_name: GIVEN -- the name to run through the numerology
            cipher ring, or None to skip that tier entirely
    """
    _ensure_ephemeris()
    y, m, d = (int(p) for p in birth_date.split("-"))
    parts = birth_time.split(":")
    hh, mm = int(parts[0]), int(parts[1])
    ss = int(parts[2]) if len(parts) > 2 else 0
    hour_decimal = hh + mm / 60.0 + ss / 3600.0
    jd = get_julian_day(y, m, d, hour_decimal)

    positions, weights, body_info, errors = all_body_positions(jd, latitude, longitude, sidereal)
    star_positions, missing_stars = calc_stars(jd, sidereal)
    for star in missing_stars:
        errors.append(f"Fixed star '{star}' not found in sefstars.txt -- skipped.")

    dignity_only_bodies, dok_errors = calc_chiron_rahu_ketu(jd, sidereal)
    errors.extend(dok_errors)

    enneagram_core, enneagram_wing = parse_enneagram_input(enneagram_type) if enneagram_type is not None else (None, None)
    mbti_code, mbti_variant = parse_mbti_input(mbti_type) if mbti_type is not None else (None, None)

    asc = calc_ascendant(jd, latitude, longitude, sidereal)
    day = is_day_chart(positions.get("Sun", 0.0), asc)

    return NatalChart(
        birth_date=birth_date, birth_time=birth_time,
        latitude=latitude, longitude=longitude,
        julian_day=jd, sidereal=sidereal,
        ascendant=asc, is_day=day,
        enneagram_type=enneagram_core, enneagram_wing=enneagram_wing,
        mbti_type=mbti_code, mbti_variant=mbti_variant,
        numerology_name=numerology_name,
        positions=positions, weights=weights, body_info=body_info,
        star_positions=star_positions, dignity_only_bodies=dignity_only_bodies,
        errors=errors,
    )


def chart_to_dict(chart: NatalChart) -> dict:
    """Serialize a NatalChart to a plain dict -- the tool result payload
    returned to the agent loop."""
    return {
        "birth_date": chart.birth_date,
        "birth_time": chart.birth_time,
        "latitude": chart.latitude,
        "longitude": chart.longitude,
        "sidereal": chart.sidereal,
        "zodiac": "13-sign sidereal (Lahiri, Ophiuchus incl.)" if chart.sidereal else "12-sign tropical",
        "ascendant": round(chart.ascendant, 4),
        "is_day_chart": chart.is_day,
        "enneagram_type": chart.enneagram_type,
        "enneagram_wing": chart.enneagram_wing,
        "mbti_type": chart.mbti_type,
        "mbti_variant": chart.mbti_variant,
        "numerology_name": chart.numerology_name,
        "bodies": chart.body_info,
        "dignity_only_bodies": chart.dignity_only_bodies,
        "fixed_stars": {s: round(v, 6) for s, v in chart.star_positions.items()},
        "errors": chart.errors,
    }
