#!/usr/bin/env python3
"""
Wealth Algorithm v2.0
═══════════════════════════════════════════════════════════════════════════════
Astrological wealth-scoring system using standard and metallic-ratio aspects.

Custom rulerships : Venus → Virgo  ·  Mercury → Libra
Custom aspects    : Supergolden  = Trine         (120.0000°)
                    Golden Angle = 360° ÷ φ²     (137.5078°)
                    Silver Angle = 360° ÷ δ²     ( 61.7317°)
                    Bronze Angle = 360° ÷ β²     ( 33.0025°)

Bodies tracked    : Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn,
                    Uranus, Neptune, Pluto, True Black Moon Lilith,
                    Lot of Fortune, Lot of Spirit, White Moon Selena
Fixed stars       : Taygeta, Arcturus, Sirius, Andromeda, Betelgeuse, Rigel,
                    Aldebaran, Fomalhaut, Antares, Regulus, Scheat, Sabik,
                    Rasalhague, Kaus Australis, Vega, Altair, Sadalsuud,
                    Zuben Elgenubi, Castor, Pollux, Spica, Hamal, Acubens,
                    Deneb Algedi, Ankaa, Deneb, Alrescha
Deep-space points : Galactic Center (SgrA*), Super Galactic Center (M87),
                    Solar Apex (LSR) — resolved via sefstars.txt like any
                    other fixed star; see STAR_FALLBACKS for the catalog
                    name each is actually stored under
Sign modes        : Tropical 12-sign  (default)
                    Sidereal Lahiri 13-sign with Ophiuchus  (--sidereal)

Install           : pip install pyswisseph
                    sefstars.txt is auto-downloaded on first run.

Usage             : python wealth_algorithm.py
                    python wealth_algorithm.py --date 1985-03-21 --time 14:30:00
                        --lat 48.8566 --lon 2.3522 --name "Marie"
                        --sidereal --output marie.json
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import csv
import json
import math
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import swisseph as swe
except ImportError:
    sys.exit("[ERROR] pyswisseph not installed.  Run: pip install pyswisseph")

try:
    import Algorithm.wealth_agent.tools.numerology as numerology
    _NUMEROLOGY_AVAILABLE = True
except ImportError:
    _NUMEROLOGY_AVAILABLE = False

try:
    import Algorithm.wealth_agent.tools.cardology as cardology
    import cosmic_calendar
    import Algorithm.wealth_agent.tools.tarot as tarot
    _CARDOLOGY_AVAILABLE = True
except ImportError:
    _CARDOLOGY_AVAILABLE = False

# cosmic_calendar hands back (suit_symbol, rank) e.g. ('♥', 'Q'); cardology
# wants compact notation e.g. 'QH'. Ranks already match (both use '10',
# 'J', 'Q', 'K', 'A'), so only the suit symbol needs translating.
_SUIT_SYMBOL_TO_LETTER: Dict[str, str] = {'♠': 'S', '♥': 'H', '♦': 'D', '♣': 'C'}


def birth_card_str(dt: datetime) -> Optional[str]:
    """
    Earth (birth) card for a date, in cardology's compact notation.
    Returns None on the cosmic Leap Day, which lands on the Joker --
    outside the 52-card Master Spreads, so no cardology profile exists
    for that one day of the cosmic year.
    """
    info = cosmic_calendar.date_to_cosmic(dt.date())
    if info is None:
        return None
    suit_symbol, rank = info["card"]
    suit = _SUIT_SYMBOL_TO_LETTER.get(suit_symbol)
    if suit is None:          # the Joker, on the Leap Day
        return None
    return f"{rank}{suit}"

# ════════════════════════════════════════════════════════════════════════════
#  METALLIC RATIO CONSTANTS
# ════════════════════════════════════════════════════════════════════════════
PHI   = (1 + math.sqrt(5)) / 2        # Golden  φ = 1.6180339887…
DELTA = 1 + math.sqrt(2)              # Silver  δ = 2.4142135624…
BETA  = (3 + math.sqrt(13)) / 2       # Bronze  β = 3.3027756377…

GOLDEN_ANGLE = 360.0 / PHI**2         # 137.5077640°
SILVER_ANGLE = 360.0 / DELTA**2       #  61.7317°
BRONZE_ANGLE = 360.0 / BETA**2        #  33.0025°

# ════════════════════════════════════════════════════════════════════════════
#  ASPECT TABLE
#  angle : exact angle (0–180°)
#  orb   : maximum orb in decimal degrees
#  score : base weight  (+ harmonious, − tense)
# ════════════════════════════════════════════════════════════════════════════
ASPECTS: Dict[str, dict] = {
    "Conjunction":    {"angle":   0.0,        "orb": 7.0,      "score": 10.0},
    "Opposition":     {"angle": 180.0,        "orb": 6.0,      "score": -6.0},
    "Trine":          {"angle": 120.0,        "orb": 6.0,      "score":  9.0},  # Supergolden
    "Square":         {"angle":  90.0,        "orb": 5.0,      "score": -5.0},
    "Sextile":        {"angle":  60.0,        "orb": 2.5,      "score":  7.0},
    "Semisquare":     {"angle":  45.0,        "orb": 1.5,      "score": -3.0},
    "Sesquiquadrate": {"angle": 135.0,        "orb": 1.5,      "score": -3.0},
    "Semisextile":    {"angle":  30.0,        "orb": 1.0,      "score":  3.0},
    "Quincunx":       {"angle": 150.0,        "orb": 1.5,      "score": -2.0},
    "Quintile":       {"angle":  72.0,        "orb": 2.0,      "score":  5.0},
    "BiQuintile":     {"angle": 144.0,        "orb": 2.0,      "score":  5.0},
    "Golden Angle":   {"angle": GOLDEN_ANGLE, "orb": 3+8/60,   "score":  8.0},
    "Silver Angle":   {"angle": SILVER_ANGLE, "orb": 3+8/60,   "score":  6.0},
    "Bronze Angle":   {"angle": BRONZE_ANGLE, "orb": 1+8/60,   "score":  5.0},
}

# ════════════════════════════════════════════════════════════════════════════
#  PLANETARY CATALOG    weight = wealth relevance (1–10)
# ════════════════════════════════════════════════════════════════════════════
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

# Computed bodies appended after the planet pass
COMPUTED_WEIGHTS: Dict[str, int] = {
    "Lot of Fortune":    10,
    "Lot of Spirit":      8,
    "White Moon Selena":  6,
}

# ════════════════════════════════════════════════════════════════════════════
#  FIXED STAR CATALOG    value = wealth relevance weight (1–10)
#  sefstars.txt name variants (all primary names work with the bundled file)
# ════════════════════════════════════════════════════════════════════════════
STAR_CATALOG: Dict[str, int] = {
    "Taygeta":        4,   # 19 Tau  — Pleiades
    "Arcturus":       7,   # al Boo
    "Sirius":         9,   # al CMa
    "Andromeda":      4,   # M31 Andromeda Galaxy (ecliptic crossing)
    "Betelgeuse":     6,   # al Ori
    "Rigel":          7,   # be Ori
    "Aldebaran":      8,   # al Tau
    "Fomalhaut":      8,   # al PsA
    "Antares":        5,   # al Sco
    "Regulus":        9,   # al Leo
    "Scheat":         3,   # be Peg
    "Sabik":          4,   # et Oph
    "Rasalhague":     4,   # al Oph
    "Kaus Australis": 6,   # ep Sgr
    "Vega":           7,   # al Lyr
    "Altair":         6,   # al Aql
    "Sadalsuud":      6,   # be Aqr
    "Zuben Elgenubi": 5,   # al-2 Lib
    # ── added: requested stars + deep-space points ─────────────────────────
    "Castor":               6,   # al Gem
    "Pollux":               6,   # be Gem
    "Spica":                9,   # al Vir — the wealth/abundance star (wheat sheaf); weighted with Sirius/Regulus
    "Hamal":                5,   # al Ari
    "Acubens":              3,   # al Cnc — faint (mag ~4.25), traditionally ill-favored
    "Deneb Algedi":         5,   # de Cap
    "Ankaa":                6,   # al Phe — the Phoenix: rebirth/transformation of fortune
    "Deneb":                7,   # al Cyg — matches Vega/Altair, its Summer Triangle companions
    "Alrescha":             4,   # al Psc
    "Galactic Center":      8,   # SgrA* — direct sefstars.txt entry, no fallback needed
    "Super Galactic Center":5,   # M87 in Virgo; niche compared to Galactic Center — see STAR_FALLBACKS
    "Solar Apex":           5,   # LSR apex, ~RA 18h04m Dec+30 (Hercules) — see STAR_FALLBACKS
}

# Fallback names tried when the primary name fails in sefstars.txt
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

# ════════════════════════════════════════════════════════════════════════════
#  ZODIAC SIGN SYSTEMS
# ════════════════════════════════════════════════════════════════════════════
SIGNS_12: List[str] = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# IAU ecliptic constellation boundaries expressed as TROPICAL longitudes.
# Subtract the Lahiri ayanamsa to obtain sidereal entry points.
_13SIGN_TROP: List[Tuple[str, float]] = [
    ("Aries",          27.86),
    ("Taurus",         53.46),
    ("Gemini",         90.33),
    ("Cancer",        119.10),
    ("Leo",           134.83),
    ("Virgo",         173.73),
    ("Libra",         217.81),
    ("Scorpio",       241.81),
    ("Ophiuchus",     247.07),   # 13th constellation; ruler = Chiron
    ("Sagittarius",   266.03),
    ("Capricorn",     299.70),
    ("Aquarius",      327.26),
    ("Pisces",        351.51),
]


def sign_tropical(lon: float) -> Tuple[str, float]:
    """12-sign tropical placement → (sign_name, degrees_within_sign)."""
    lon = lon % 360.0
    return SIGNS_12[int(lon // 30)], lon % 30.0


def sign_sidereal_13(sid_lon: float, ayanamsa: float) -> Tuple[str, float]:
    """
    13-sign sidereal placement using IAU boundaries (Ophiuchus included).
    Algorithm: largest boundary entry ≤ sid_lon wins; Pisces is the
    default because it wraps past 0°.
    """
    entries = [(n, (t - ayanamsa) % 360.0) for n, t in _13SIGN_TROP]
    sid_lon = sid_lon % 360.0
    result_name, result_start = entries[-1]          # Pisces wraps 0°
    for name, start in entries:
        if sid_lon >= start:
            result_name, result_start = name, start
    return result_name, (sid_lon - result_start) % 360.0


# ════════════════════════════════════════════════════════════════════════════
#  DIGNITY SYSTEM
#  Custom rulerships: Venus → Virgo  ·  Mercury → Libra
# ════════════════════════════════════════════════════════════════════════════
_OPP: Dict[str, str] = {s: SIGNS_12[(i + 6) % 12] for i, s in enumerate(SIGNS_12)}

RULERSHIPS: Dict[str, List[str]] = {
    "Sun":      ["Leo"],
    "Moon":     ["Cancer"],
    "Mercury":  ["Gemini", "Libra"],         # Libra: custom
    "Venus":    ["Taurus", "Virgo"],          # Virgo: custom
    "Mars":     ["Aries", "Scorpio"],
    "Jupiter":  ["Sagittarius", "Pisces"],
    "Saturn":   ["Capricorn", "Aquarius"],
    "Uranus":   ["Aquarius"],
    "Neptune":  ["Pisces"],
    "Pluto":    ["Scorpio"],
}

EXALTATIONS: Dict[str, str] = {
    "Sun":     "Aries",     "Moon":    "Taurus",    "Mercury": "Virgo",
    "Venus":   "Pisces",    "Mars":    "Capricorn",  "Jupiter": "Cancer",
    "Saturn":  "Libra",     "Uranus":  "Scorpio",   "Neptune": "Leo",
    "Pluto":   "Aries",
}

DETRIMENTS: Dict[str, List[str]] = {
    p: [_OPP[s] for s in signs if s in _OPP]
    for p, signs in RULERSHIPS.items()
}

FALLS: Dict[str, str] = {
    p: _OPP[s] for p, s in EXALTATIONS.items() if s in _OPP
}

DIGNITY_SCORE: Dict[str, float] = {
    "rulership":  3.0,
    "exaltation": 1.5,
    "fall":      -1.0,
    "detriment": -2.0,
}

DIG_SYMBOL: Dict[str, str] = {
    "rulership": "★", "exaltation": "▲", "fall": "▼", "detriment": "✗", "": " ",
}


def planet_dignity(planet: str, sign: str) -> str:
    """'rulership' | 'exaltation' | 'fall' | 'detriment' | ''"""
    if sign in RULERSHIPS.get(planet, []):   return "rulership"
    if sign in DETRIMENTS.get(planet, []):   return "detriment"
    if sign == EXALTATIONS.get(planet):      return "exaltation"
    if sign == FALLS.get(planet):            return "fall"
    return ""


# ════════════════════════════════════════════════════════════════════════════
#  FORMATTING HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _dms(deg: float) -> str:
    """Decimal degrees → D°MM'SS" string."""
    d = int(deg)
    rem = (deg - d) * 60
    m = int(rem)
    s = round((rem - m) * 60)
    if s == 60: m += 1; s = 0
    if m == 60: d += 1; m = 0
    return f"{d}°{m:02d}'{s:02d}\""


def _coord(lat: float, lon: float) -> str:
    return (f"{'N' if lat >= 0 else 'S'}{abs(lat):.4f}  "
            f"{'E' if lon >= 0 else 'W'}{abs(lon):.4f}")


def _log_entry(pair: str, kind: str, asp: str,
               orb: float, strength: float, contrib: float) -> dict:
    return {
        "pair":     pair,
        "type":     kind,
        "aspect":   asp,
        "orb":      round(orb, 4),
        "orb_dms":  _dms(orb),
        "strength": round(strength, 3),
        "contrib":  round(contrib, 3),
    }


# ════════════════════════════════════════════════════════════════════════════
#  EPHEMERIS SETUP
#  sefstars.txt is required for fixed-star lookups.
#  On first run it is auto-downloaded from the Swiss Ephemeris repository.
# ════════════════════════════════════════════════════════════════════════════
_SEFSTARS_URL = (
    "https://github.com/aloistr/swisseph/raw/master/ephe/sefstars.txt"
)


def setup_ephemeris(ephe_dir: Optional[str] = None) -> None:
    """
    Locate (or create) the ephemeris directory and register it with
    pyswisseph.  Downloads sefstars.txt automatically if absent.
    Priority:
      1. --ephe-path CLI argument
      2. ephe/ folder next to this script   (default)
    """
    if ephe_dir:
        ephe_path = Path(ephe_dir).expanduser().resolve()
    else:
        ephe_path = Path(__file__).parent / "ephe"

    ephe_path.mkdir(parents=True, exist_ok=True)
    stars_file = ephe_path / "sefstars.txt"

    if not stars_file.exists():
        print("  sefstars.txt not found — downloading from Swiss Ephemeris …")
        try:
            urllib.request.urlretrieve(_SEFSTARS_URL, str(stars_file))
            print(f"  ✓  sefstars.txt saved → {ephe_path}")
        except Exception as exc:
            print(f"  [!] Download failed: {exc}")
            print(f"      Fixed stars unavailable.")
            print(f"      Manual download URL: {_SEFSTARS_URL}")

    swe.set_ephe_path(str(ephe_path))


def get_julian_day(dt: datetime) -> float:
    """UTC datetime → Julian Day Number."""
    return swe.julday(dt.year, dt.month, dt.day,
                      dt.hour + dt.minute / 60.0 + dt.second / 3600.0)


# ════════════════════════════════════════════════════════════════════════════
#  POSITION CALCULATIONS
# ════════════════════════════════════════════════════════════════════════════
def calc_planets(
    jd: float, sidereal: bool = False
) -> Tuple[Dict[str, float], Dict[str, bool]]:
    """
    Ecliptic longitudes + retrograde flags for all catalog planets.
    xx[3] is longitudinal speed; negative = retrograde.
    Returns (longitudes_dict, retrograde_dict).
    """
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL

    lons:  Dict[str, float] = {}
    retro: Dict[str, bool]  = {}
    for name, data in PLANET_CATALOG.items():
        xx, _ = swe.calc_ut(jd, data["id"], flags)
        lons[name]  = xx[0] % 360.0
        retro[name] = xx[3] < 0.0          # negative speed → retrograde
    return lons, retro


def calc_ascendant(jd: float, lat: float, lon: float,
                   sidereal: bool = False) -> float:
    """
    Placidus Ascendant.  In sidereal mode the tropical value is corrected
    by subtracting the Lahiri ayanamsa.
    """
    _, ascmc = swe.houses(jd, lat, lon, b"P")
    asc = ascmc[0]
    if sidereal:
        asc = (asc - swe.get_ayanamsa_ut(jd)) % 360.0
    return asc


def is_day_chart(sun_lon: float, asc: float) -> bool:
    """True when the Sun is above the horizon (houses 7–12)."""
    return ((sun_lon - asc) % 360.0) > 180.0


def calc_lots(asc: float, sun: float, moon: float, day: bool) -> Dict[str, float]:
    """
    Hellenistic Lots with Ptolemaic day/night reversal.
      Day  → Fortune = ASC + Moon − Sun    Spirit = ASC + Sun  − Moon
      Night → Fortune = ASC + Sun  − Moon   Spirit = ASC + Moon − Sun
    """
    if day:
        return {"Lot of Fortune": (asc + moon - sun) % 360.0,
                "Lot of Spirit":  (asc + sun  - moon) % 360.0}
    return     {"Lot of Fortune": (asc + sun  - moon) % 360.0,
                "Lot of Spirit":  (asc + moon - sun)  % 360.0}


def calc_selena(bml_lon: float) -> float:
    """
    True White Moon Selena = True Black Moon Lilith + 180°.
    Selena (perigee) and Lilith (apogee) are always opposite.
    """
    return (bml_lon + 180.0) % 360.0


def _fetch_star(name: str, jd: float, flags: int) -> Optional[float]:
    """
    Resolve a fixed star longitude.  Tries the primary catalog name first,
    then the fallback.  swe.fixstar_ut() returns a 3-tuple:
        (xx_array, matched_name_str, return_flags)
    """
    candidates = [name]
    if name in STAR_FALLBACKS:
        candidates.append(STAR_FALLBACKS[name])
    for candidate in candidates:
        try:
            xx, _sname, _ret = swe.fixstar_ut(candidate, jd, flags)
            return xx[0] % 360.0
        except Exception:
            pass
    print(f"  [!] Fixed star '{name}' not found in sefstars.txt — skipped.")
    return None


def calc_stars(jd: float) -> Dict[str, float]:
    """Ecliptic longitudes for all 30 catalog fixed stars/points."""
    flags = swe.FLG_SWIEPH
    out:  Dict[str, float] = {}
    for name in STAR_CATALOG:
        lon = _fetch_star(name, jd, flags)
        if lon is not None:
            out[name] = lon
    return out


# BodyInfo keys: lon, sign, deg_in_sign, retro
BodyInfo = Dict


def all_body_positions(
    jd: float, lat: float, lon: float, sidereal: bool = False
) -> Tuple[Dict[str, float], Dict[str, int], Dict[str, BodyInfo]]:
    """
    Compute every tracked body (11 planets + 3 computed points).
    Returns:
      positions  {name → longitude}          → aspect / scoring engine
      weights    {name → int}                → scoring engine
      body_info  {name → {lon,sign,deg,retro}} → display / export
    """
    lons, retro = calc_planets(jd, sidereal)

    # Ayanamsa is set by calc_planets when sidereal=True.
    ayana = swe.get_ayanamsa_ut(jd) if sidereal else 0.0

    asc = calc_ascendant(jd, lat, lon, sidereal)
    day = is_day_chart(lons["Sun"], asc)

    lons.update(calc_lots(asc, lons["Sun"], lons["Moon"], day))
    lons["White Moon Selena"] = calc_selena(lons["True BML"])

    weights = {n: d["weight"] for n, d in PLANET_CATALOG.items()}
    weights.update(COMPUTED_WEIGHTS)

    info: Dict[str, BodyInfo] = {}
    for name, body_lon in lons.items():
        if sidereal:
            sign, deg = sign_sidereal_13(body_lon, ayana)
        else:
            sign, deg = sign_tropical(body_lon)
        info[name] = {
            "lon":         round(body_lon, 4),
            "sign":        sign,
            "deg_in_sign": round(deg, 2),
            "retro":       retro.get(name, False),
        }

    return lons, weights, info


# ════════════════════════════════════════════════════════════════════════════
#  ASPECT ENGINE
# ════════════════════════════════════════════════════════════════════════════
AspectHit = Tuple[str, float, float]   # (aspect_name, actual_orb, base_score)


def short_arc(lon1: float, lon2: float) -> float:
    """Minimum arc between two ecliptic longitudes (always 0–180°)."""
    diff = abs(lon1 - lon2) % 360.0
    return min(diff, 360.0 - diff)


def detect_aspects(lon1: float, lon2: float) -> List[AspectHit]:
    """All aspects triggered between two positions."""
    sep  = short_arc(lon1, lon2)
    hits: List[AspectHit] = []
    for name, asp in ASPECTS.items():
        delta = abs(sep - asp["angle"])
        if delta <= asp["orb"]:
            hits.append((name, delta, asp["score"]))
    return hits


def orb_strength(actual: float, maximum: float) -> float:
    """Linear orb-strength: 1.0 at exact aspect, 0.0 at the orb boundary."""
    return 1.0 - (actual / maximum)


# ════════════════════════════════════════════════════════════════════════════
#  SCORING ENGINE
#
#  Planet-Planet : base_score × avg_weight × orb_strength
#  Planet-Star   : base_score × avg_weight × orb_strength × STAR_FACTOR
# ════════════════════════════════════════════════════════════════════════════
STAR_FACTOR = 0.70   # fixed stars contribute slightly less than moving planets


def score_aspects(
    planet_pos: Dict[str, float],
    planet_wts: Dict[str, int],
    star_pos:   Dict[str, float],
) -> Tuple[float, List[dict]]:
    """Score all planet–planet and planet–star aspect pairs."""
    total = 0.0
    log:  List[dict] = []
    bodies = list(planet_pos.keys())

    # Planet–planet
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            b1, b2 = bodies[i], bodies[j]
            w_avg  = (planet_wts[b1] + planet_wts[b2]) / 2.0
            for asp, orb_used, base in detect_aspects(planet_pos[b1], planet_pos[b2]):
                sf = orb_strength(orb_used, ASPECTS[asp]["orb"])
                c  = base * w_avg * sf
                total += c
                log.append(_log_entry(f"{b1} / {b2}", "P-P", asp, orb_used, sf, c))

    # Planet–star
    for planet, plon in planet_pos.items():
        pw = planet_wts[planet]
        for star, slon in star_pos.items():
            sw    = STAR_CATALOG.get(star, 5)
            w_avg = (pw + sw) / 2.0
            for asp, orb_used, base in detect_aspects(plon, slon):
                sf = orb_strength(orb_used, ASPECTS[asp]["orb"])
                c  = base * w_avg * sf * STAR_FACTOR
                total += c
                log.append(_log_entry(f"{planet} / {star}", "P-S", asp, orb_used, sf, c))

    log.sort(key=lambda x: abs(x["contrib"]), reverse=True)
    return total, log


def score_dignities(
    planet_pos: Dict[str, float],
    planet_wts: Dict[str, int],
    body_info:  Dict[str, BodyInfo],
) -> Tuple[float, List[dict]]:
    """
    Per-planet dignity/debility bonus:
        DIGNITY_SCORE[status] × planet_weight
    Only planets with defined rulerships are evaluated.
    """
    total = 0.0
    log:  List[dict] = []
    for planet in RULERSHIPS:
        if planet not in planet_pos or planet not in body_info:
            continue
        sign    = body_info[planet]["sign"]
        dignity = planet_dignity(planet, sign)
        if not dignity:
            continue
        bonus  = DIGNITY_SCORE[dignity] * planet_wts.get(planet, 1)
        total += bonus
        log.append({
            "planet":  planet,
            "sign":    sign,
            "dignity": dignity,
            "bonus":   round(bonus, 2),
        })
    return total, log


def normalize(raw: float, lo: float = -600.0, hi: float = 1200.0) -> float:
    """Map raw score → 0–100.  Tune lo/hi after calibrating on many charts."""
    return max(0.0, min(100.0, (raw - lo) / (hi - lo) * 100.0))


def rating_label(s: float) -> str:
    if s >= 80: return "Exceptional"
    if s >= 65: return "Strong"
    if s >= 50: return "Moderate"
    if s >= 35: return "Developing"
    return "Challenging"


# ════════════════════════════════════════════════════════════════════════════
#  EXPORT  (JSON · CSV)
# ════════════════════════════════════════════════════════════════════════════
def export_results(
    outpath:     str,
    name:        str,
    dt:          datetime,
    lat:         float,
    lon:         float,
    body_info:   Dict[str, BodyInfo],
    star_pos:    Dict[str, float],
    aspect_log:  List[dict],
    dignity_log: List[dict],
    raw:         float,
    norm:        float,
    sidereal:    bool,
    num_boost:   float = 0.0,
    num_log:     Optional[List[dict]] = None,
    num_profile: Optional["numerology.NumerologyProfile"] = None,
    cosmic_cards: Optional["cardology.CosmicCardProfile"] = None,
    tarot_cards: Optional["tarot.TarotCardProfile"] = None,
) -> None:
    ext = Path(outpath).suffix.lower()

    if ext == ".json":
        payload = {
            "meta": {
                "name":         name,
                "datetime_utc": dt.isoformat(),
                "latitude":     lat,
                "longitude":    lon,
                "mode": "sidereal_lahiri_13sign" if sidereal else "tropical_12sign",
            },
            "bodies":      body_info,
            "fixed_stars": {s: {"lon": round(v, 4)} for s, v in star_pos.items()},
            "aspects":     aspect_log,
            "dignities":   dignity_log,
            "numerology": ({
                "name":              num_profile.name,
                "life_path":         num_profile.life_path,
                "life_path_planet":  num_profile.life_path_planet,
                "ciphers":           num_log,
                "boost":             round(num_boost, 3),
            } if num_profile else None),
            "cosmic_cards": (cosmic_cards.as_dict() if cosmic_cards else None),
            "cosmic_card_numbers": ({
                field: tarot.cosmic_card_number(getattr(cosmic_cards, field))
                for field in cosmic_cards.__dataclass_fields__
            } if cosmic_cards else None),
            "tarot_cards": (tarot_cards.as_dict() if tarot_cards else None),
            "score": {
                "raw":        round(raw, 3),
                "normalized": round(norm, 1),
                "rating":     rating_label(norm),
            },
        }
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"  ✓  JSON saved → {outpath}")

    elif ext == ".csv":
        fields = ["pair", "type", "aspect", "orb", "orb_dms", "strength", "contrib"]
        with open(outpath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(aspect_log)
        print(f"  ✓  CSV  saved → {outpath}")

    else:
        print(f"  [!] Unknown output format '{ext}'.  Use .json or .csv")


# ════════════════════════════════════════════════════════════════════════════
#  REPORT
# ════════════════════════════════════════════════════════════════════════════
def print_report(
    name:        str,
    dt:          datetime,
    lat:         float,
    lon:         float,
    body_info:   Dict[str, BodyInfo],
    star_pos:    Dict[str, float],
    aspect_log:  List[dict],
    dignity_log: List[dict],
    raw:         float,
    norm:        float,
    dig_bonus:   float,
    sidereal:    bool,
    top_n:       int,
    num_boost:   float = 0.0,
    num_log:     Optional[List[dict]] = None,
    num_profile: Optional["numerology.NumerologyProfile"] = None,
    cosmic_cards: Optional["cardology.CosmicCardProfile"] = None,
    tarot_cards: Optional["tarot.TarotCardProfile"] = None,
) -> None:
    num_log = num_log or []
    W    = 82
    bar  = "─" * W
    dbar = "═" * W
    mode = ("Sidereal · Lahiri · 13-Sign (IAU / Ophiuchus)"
            if sidereal else "Tropical · 12-Sign")

    print(f"\n{dbar}")
    print(f"  WEALTH ALGORITHM  ·  {name}")
    print(f"{dbar}")
    print(f"  Date / Time  : {dt.strftime('%Y-%m-%d  %H:%M:%S')} UTC")
    print(f"  Location     : {_coord(lat, lon)}")
    print(f"  Mode         : {mode}")
    print(f"{bar}")

    sign_hdr = "CONSTELLATION" if sidereal else "SIGN"

    # ── Body positions ────────────────────────────────────────────────────
    print(f"\n  {'BODY':<22} {'LONGITUDE':>10}  {sign_hdr:<16}  {'IN SIGN':>7}  DIG  R")
    print(f"  {'─'*72}")
    for body, info in body_info.items():
        dig  = planet_dignity(body, info["sign"])
        dsym = DIG_SYMBOL[dig]
        rsym = "℞" if info["retro"] else " "
        print(f"  {body:<22} {info['lon']:>10.4f}°  {info['sign']:<16}"
              f"  {info['deg_in_sign']:>6.2f}°  {dsym:<3}  {rsym}")

    # ── Fixed stars ───────────────────────────────────────────────────────
    print(f"\n  {'FIXED STAR':<22} {'LONGITUDE':>10}   WT")
    print(f"  {'─'*38}")
    if star_pos:
        for star, slon in star_pos.items():
            print(f"  {star:<22} {slon:>10.4f}°   {STAR_CATALOG[star]}")
    else:
        print("  (none resolved — check ephe/sefstars.txt)")

    # ── Dignities ─────────────────────────────────────────────────────────
    if dignity_log:
        print(f"\n  DIGNITIES & DEBILITIES  (Venus→Virgo · Mercury→Libra)")
        print(f"  {'─'*58}")
        for d in dignity_log:
            sym = DIG_SYMBOL[d["dignity"]]
            print(f"  {sym}  {d['planet']:<14} in {d['sign']:<16}  "
                  f"{d['dignity']:<12}  {d['bonus']:>+7.2f}")
        print(f"  {'─'*58}")
        print(f"  {'Dignity sub-total':<48}  {dig_bonus:>+7.2f}")

    # ── Aspect log ────────────────────────────────────────────────────────
    pos_ct = sum(1 for e in aspect_log if e["contrib"] > 0)
    neg_ct = sum(1 for e in aspect_log if e["contrib"] < 0)
    print(f"\n  TOP {top_n} ASPECTS BY WEALTH CONTRIBUTION")
    print(f"  Detected: {len(aspect_log)} total  "
          f"( +{pos_ct} harmonious  /  −{neg_ct} tense )")
    print()
    print(f"  {'PAIR':<36} {'ASPECT':<16} {'ORB':>7} {'STR':>5} {'SCORE':>8}")
    print(f"  {'─'*W}")
    for e in aspect_log[:top_n]:
        print(f"  {e['pair']:<36} {e['aspect']:<16}"
              f" {e['orb_dms']:>7} {e['strength']:>5.2f}"
              f" {e['contrib']:>+8.2f}")

    # ── Score by aspect type ──────────────────────────────────────────────
    asp_totals: Dict[str, float] = {}
    for e in aspect_log:
        asp_totals[e["aspect"]] = asp_totals.get(e["aspect"], 0.0) + e["contrib"]
    sorted_asps = sorted(asp_totals.items(), key=lambda x: abs(x[1]), reverse=True)

    print(f"\n  SCORE BY ASPECT TYPE")
    print(f"  {'─'*54}")
    for asp_name, asp_tot in sorted_asps:
        bar_len = int(abs(asp_tot) / 5)
        bar_sym = ("█" * min(bar_len, 34)) if asp_tot >= 0 else ("░" * min(bar_len, 34))
        print(f"  {asp_name:<18} {asp_tot:>+8.2f}  {bar_sym}")

    # ── Numerology ────────────────────────────────────────────────────────
    if num_log:
        print(f"\n  NUMEROLOGY  ·  Life Path {num_profile.life_path}"
              f" → {num_profile.life_path_planet}"
              f"  ({num_profile.name})")
        print(f"  {'─'*66}")
        print(f"  {'CIPHER':<24} {'#':>4} {'M':>2}  {'PLANET':<10} {'SIGNAL':>8} {'CONTRIB':>9}")
        for e in num_log:
            m = "✦" if e["master"] else " "
            print(f"  {e['cipher']:<24} {e['reduced']:>4} {m:>2}  "
                  f"{e['planet']:<10} {e['signal']:>+8.2f} {e['contrib']:>+9.3f}")
        print(f"  {'─'*66}")
        print(f"  {'Numerology sub-total':<48}  {num_boost:>+7.2f}")
        print(f"  (✦ = master number — amplified {numerology.MASTER_NUMBER_AMPLIFIER}× via MASTER_NUMBER_AMPLIFIER)")

    # ── Cosmic playing cards + Tarot equivalents ─────────────────────────
    if cosmic_cards:
        cc, tc = cosmic_cards, tarot_cards
        print(f"\n  COSMIC PLAYING CARDS  ·  Earth {cc.earth.symbol}  ({cc.earth.full_name})")
        print(f"  {'─'*76}")
        print(f"  {'POINT':<18} {'CARD':<6} {'TAROT EQUIVALENT':<20} {'#':>3}   COSMIC #")
        print(f"  {'─'*76}")
        rows = [("Sun (spirit card)", "sun"), ("Karma", "karma"), ("Moon", "moon")]
        rows += [(label.capitalize(), label) for label in (
            "mercury", "venus", "mars", "jupiter", "saturn", "uranus",
            "neptune", "pluto", "chiron", "rahu", "midheaven", "phoenix")]
        for label, field in rows:
            c = getattr(cc, field)
            t = getattr(tc, field) if tc else None
            t_name = t.name if t else "—"
            t_num  = str(t.number) if t and t.number is not None else "—"
            print(f"  {label:<18} {c.symbol:<6} {t_name:<20} {t_num:>3}   "
                  f"{tarot.cosmic_card_number(c) if tc else '—'}")
        print(f"  {'─'*76}")
        print(f"  (not folded into the wealth score — see cardology.py / tarot.py)")
        print(f"  (# = teachmetarot.com index, 0–78  ·  COSMIC # = itsallinthecards.com index, 0–53)")

    # ── Final score ───────────────────────────────────────────────────────
    asp_total = sum(asp_totals.values())
    print(f"\n{dbar}")
    print(f"  ASPECT SCORE       :  {asp_total:>+10.2f}")
    print(f"  DIGNITY BONUS      :  {dig_bonus:>+10.2f}")
    if num_log:
        print(f"  NUMEROLOGY BOOST   :  {num_boost:>+10.2f}")
    print(f"  {'─'*32}")
    print(f"  RAW WEALTH SCORE   :  {raw:>+10.2f}")
    print(f"  NORMALIZED (0–100) :  {norm:>10.1f}")
    print(f"  RATING             :  {rating_label(norm)}")
    print(f"{dbar}")
    print()


# ════════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════════
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wealth_algorithm",
        description="Astrological wealth score — metallic-ratio aspect system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python wealth_algorithm.py\n"
            "  python wealth_algorithm.py --date 1990-06-15 --time 14:30:00"
            " --lat 40.71 --lon -74.01 --name Alice\n"
            "  python wealth_algorithm.py --date 1990-06-15 --time 14:30:00"
            " --lat 40.71 --lon -74.01 --sidereal --output alice.json\n"
        ),
    )
    p.add_argument("--name",      default=None,
                   help="Name of native")
    p.add_argument("--date",      default=None,
                   help="Birth date  YYYY-MM-DD  (UTC)")
    p.add_argument("--time",      default=None,
                   help="Birth time  HH:MM:SS   (UTC, 24-hour)")
    p.add_argument("--lat",       type=float,
                   help="Latitude   (N positive, S negative)")
    p.add_argument("--lon",       type=float,
                   help="Longitude  (E positive, W negative)")
    p.add_argument("--sidereal",  action="store_true",
                   help="Use Lahiri sidereal + 13-sign (IAU/Ophiuchus) mode")
    p.add_argument("--top",       type=int, default=40,
                   help="Number of top aspects to print  (default: 40)")
    p.add_argument("--output",    default=None,
                   help="Export results: path ending in .json or .csv")
    p.add_argument("--ephe-path", default=None, dest="ephe_path",
                   help="Custom ephemeris directory (default: ephe/ next to script)")
    p.add_argument("--cipher-js", default=None, dest="cipher_js",
                   help="Path to ciphers.js (default: next to this script)")
    p.add_argument("--numerology-name", default=None, dest="numerology_name",
                   help="Name to run through the numerology ring, if different"
                        " from --name (e.g. full legal name)")
    p.add_argument("--no-numerology", action="store_true", dest="no_numerology",
                   help="Skip the numerology scoring tier entirely")
    return p


def _prompt(label: str, default: Optional[str] = None) -> str:
    sfx = f" [{default}]" if default else ""
    val = input(f"  {label}{sfx}: ").strip()
    return val if val else (default or "")


def main() -> None:
    args = _build_parser().parse_args()
    setup_ephemeris(args.ephe_path)

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   WEALTH ALGORITHM  v2.0                     ║")
    print("║   Metallic-Ratio Aspect System               ║")
    print("║   Venus → Virgo  ·  Mercury → Libra          ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    name     = args.name  or _prompt("Name", "Native")
    date_str = args.date  or _prompt("Birth date (YYYY-MM-DD)")
    time_str = args.time  or _prompt("Birth time UTC (HH:MM:SS)", "12:00:00")
    lat      = args.lat   if args.lat  is not None else float(_prompt("Latitude  (N positive)"))
    lon_in   = args.lon   if args.lon  is not None else float(_prompt("Longitude (E positive)"))
    sidereal = args.sidereal
    top_n    = args.top
    outpath  = args.output

    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        sys.exit(f"[ERROR] Date/time parse error: {exc}")

    jd = get_julian_day(dt)

    print("  Calculating body positions …")
    planet_pos, planet_wts, body_info = all_body_positions(jd, lat, lon_in, sidereal)

    print("  Retrieving fixed star positions …")
    star_pos = calc_stars(jd)

    print("  Scoring aspects and dignities …")
    asp_score,  aspect_log  = score_aspects(planet_pos, planet_wts, star_pos)
    dig_bonus,  dignity_log = score_dignities(planet_pos, planet_wts, body_info)

    num_boost, num_log, num_profile = 0.0, [], None
    if args.no_numerology:
        pass
    elif not _NUMEROLOGY_AVAILABLE:
        print("  [!] Numerology: numerology.py not found alongside this script — skipped.")
    else:
        print("  Scoring numerology ring …")
        cipher_js   = args.cipher_js or str(Path(__file__).parent / "ciphers.js")
        numer_name  = args.numerology_name or name
        try:
            num_profile = numerology.compute_numerology_profile(
                numer_name, (dt.year, dt.month, dt.day), cipher_js)
            num_boost, num_log = numerology.score_numerology_boost(
                num_profile, aspect_log, dignity_log)
        except FileNotFoundError:
            print(f"  [!] Numerology: cipher file not found at {cipher_js} — skipped.")
        except Exception as exc:
            print(f"  [!] Numerology: {exc} — skipped.")

    cosmic_cards = None
    if not _CARDOLOGY_AVAILABLE:
        print("  [!] Cardology: cardology.py / cosmic_calendar.py not found alongside"
              " this script — skipped.")
    else:
        print("  Deriving cosmic playing cards …")
        earth = birth_card_str(dt)
        if earth is None:
            print("  [!] Cardology: birth date falls on the cosmic Leap Day (the"
                  " Joker) — no Master Spread position exists, skipped.")
        else:
            cosmic_cards = cardology.derive_cosmic_cards(earth)

    tarot_cards = tarot.derive_tarot_profile(cosmic_cards) if cosmic_cards else None

    # Cardology/Tarot are reported alongside the chart, not folded into the
    # score. If you want them to contribute, the natural spot is right
    # here, added into `raw` before normalize() — the same
    # additive-before-normalization pattern num_boost uses above — once
    # you've defined what a given card/suit/arcana is actually worth.
    raw  = asp_score + dig_bonus + num_boost
    norm = normalize(raw)

    print_report(
        name, dt, lat, lon_in,
        body_info, star_pos,
        aspect_log, dignity_log,
        raw, norm, dig_bonus,
        sidereal, top_n,
        num_boost, num_log, num_profile,
        cosmic_cards, tarot_cards,
    )

    if outpath:
        export_results(
            outpath, name, dt, lat, lon_in,
            body_info, star_pos,
            aspect_log, dignity_log,
            raw, norm, sidereal,
            num_boost, num_log, num_profile,
            cosmic_cards, tarot_cards,
        )


if __name__ == "__main__":
    main()
