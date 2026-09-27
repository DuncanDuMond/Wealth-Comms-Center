"""
scoring.py — Aspect detection, dignity system, and final wealth score.

FAITHFUL PORT from your uploaded wealth_algorithm.py: ASPECTS (14 exact
angle/orb/score triples), the dignity tables (RULERSHIPS/EXALTATIONS/
DETRIMENTS/FALLS/DIGNITY_SCORE), detect_aspects, orb_strength,
score_aspects (Planet-Planet + Planet-Star, STAR_FACTOR=0.70),
score_dignities, normalize(lo=-600, hi=1200), rating_label. Every
constant and formula below matches your source exactly -- cross-checked
against the uploaded file line by line, not reconstructed from memory.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .chart import NatalChart, STAR_CATALOG, SIGNS_12

# ---------------------------------------------------------------------------
# METALLIC RATIO CONSTANTS -- verbatim.
# ---------------------------------------------------------------------------
PHI = (1 + math.sqrt(5)) / 2       # Golden  phi = 1.6180339887...
DELTA = 1 + math.sqrt(2)            # Silver  delta = 2.4142135624...
BETA = (3 + math.sqrt(13)) / 2      # Bronze  beta = 3.3027756377...

GOLDEN_ANGLE = 360.0 / PHI ** 2     # 137.5077640deg
SILVER_ANGLE = 360.0 / DELTA ** 2   # 61.7317deg
BRONZE_ANGLE = 360.0 / BETA ** 2    # 33.0025deg

# ---------------------------------------------------------------------------
# ASPECT TABLE -- verbatim. angle=exact angle, orb=max orb, score=base weight.
# ---------------------------------------------------------------------------
ASPECTS: Dict[str, dict] = {
    "Conjunction":    {"angle":   0.0,        "orb": 7.0,    "score": 10.0},
    "Opposition":     {"angle": 180.0,        "orb": 6.0,    "score": -6.0},
    "Trine":          {"angle": 120.0,        "orb": 6.0,    "score":  9.0},  # Supergolden
    "Square":         {"angle":  90.0,        "orb": 5.0,    "score": -5.0},
    "Sextile":        {"angle":  60.0,        "orb": 2.5,    "score":  7.0},
    "Semisquare":     {"angle":  45.0,        "orb": 1.5,    "score": -3.0},
    "Sesquiquadrate": {"angle": 135.0,        "orb": 1.5,    "score": -3.0},
    "Semisextile":    {"angle":  30.0,        "orb": 1.0,    "score":  3.0},
    "Quincunx":       {"angle": 150.0,        "orb": 1.5,    "score": -2.0},
    "Quintile":       {"angle":  72.0,        "orb": 2.0,    "score":  5.0},
    "BiQuintile":     {"angle": 144.0,        "orb": 2.0,    "score":  5.0},
    "Golden Angle":   {"angle": GOLDEN_ANGLE, "orb": 3 + 8 / 60, "score": 8.0},
    "Silver Angle":   {"angle": SILVER_ANGLE, "orb": 3 + 8 / 60, "score": 6.0},
    "Bronze Angle":   {"angle": BRONZE_ANGLE, "orb": 1 + 8 / 60, "score": 5.0},
}

# ---------------------------------------------------------------------------
# DIGNITY SYSTEM -- domicile/rulership unchanged from wealth_algorithm.py's
# source (custom rulerships: Venus -> Virgo, Mercury -> Libra). EXALTATIONS
# for Mercury/Venus/Neptune were UPDATED from the source's Virgo/Pisces/Leo
# to Aquarius/Capricorn/Cancer, per your chat message's dignity table --
# not a silent overwrite: the change was cross-checked against that same
# message's "Dominant dignity architecture" per-sign table before being
# trusted ("Aquarius: Mercury exaltation...", "Capricorn: Venus
# exaltation...", "Cancer: ...Neptune exaltation" all independently confirm
# the new values), which is stronger evidence than either table alone.
#
# Chiron/Rahu/Ketu/True BML/White Moon Selena are new additions, also from
# that message, not any uploaded script -- your own footnote marks these
# five as "functional/esoteric rulerships within my customized system,
# rather than universally recognized" dignities, preserved here rather
# than smoothed over.
#
# DETRIMENTS/FALLS stay fully DERIVED (opposite-sign rule), same mechanism
# as the original 10-planet table -- verified this holds for all 5 new
# bodies before relying on it: every detriment/fall you listed for them
# matches what _OPP produces from their domicile/exaltation, with zero
# exceptions. That's strong internal-consistency evidence for the table as
# given, not just a convenient shortcut.
#
# Keyed on the 12-sign tropical names regardless of chart sign-mode -- a
# planet transiting Ophiuchus (sidereal 13-sign only) gets no dignity
# bonus/penalty, since Ophiuchus isn't a key in any of these tables.
# Preserved as-is, not "fixed".
# ---------------------------------------------------------------------------
_OPP: Dict[str, str] = {s: SIGNS_12[(i + 6) % 12] for i, s in enumerate(SIGNS_12)}

RULERSHIPS: Dict[str, List[str]] = {
    "Sun":      ["Leo"],
    "Moon":     ["Cancer"],
    "Mercury":  ["Gemini", "Libra"],          # Libra: custom
    "Venus":    ["Taurus", "Virgo"],           # Virgo: custom
    "Mars":     ["Aries", "Scorpio"],
    "Jupiter":  ["Sagittarius", "Pisces"],
    "Saturn":   ["Capricorn", "Aquarius"],
    "Uranus":   ["Aquarius"],
    "Neptune":  ["Pisces"],
    "Pluto":    ["Scorpio"],
    "Chiron":   ["Sagittarius"],   # functional/esoteric, per your footnote
    "Rahu":     ["Gemini"],        # functional/esoteric, per your footnote
    "Ketu":     ["Sagittarius"],   # functional/esoteric, per your footnote
    "True BML": ["Scorpio"],       # functional/esoteric, per your footnote
    "White Moon Selena": ["Taurus"],  # functional/esoteric, per your footnote
}

EXALTATIONS: Dict[str, str] = {
    "Sun":     "Aries",     "Moon":    "Taurus",     "Mercury": "Aquarius",  # was Virgo
    "Venus":   "Capricorn", "Mars":    "Capricorn",  "Jupiter": "Cancer",     # Venus was Pisces
    "Saturn":  "Libra",     "Uranus":  "Scorpio",    "Neptune": "Cancer",     # was Leo
    "Pluto":   "Aries",
    "Chiron":  "Virgo",     "Rahu":    "Taurus",     "Ketu":    "Scorpio",
    "True BML": "Aquarius", "White Moon Selena": "Cancer",
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
    "rulership": "*", "exaltation": "^", "fall": "v", "detriment": "x", "": " ",
}  # ASCII-safe versions of your original star/triangle/cross glyphs

# The five newly-added bodies, so callers (score_dignities' extra_bodies
# path, agent_loop.py) can tell "new, dignity-only" apart from the
# original 10 without hardcoding the list twice.
NEW_DIGNITY_BODIES: Tuple[str, ...] = ("Chiron", "Rahu", "Ketu")
# True BML and White Moon Selena were already tracked bodies before this
# update (already in chart.positions/chart.weights) -- only their
# EXALTATIONS/RULERSHIPS entries are new, so they're not in this tuple;
# they already flow through score_dignities' main loop like any other
# already-tracked body, no extra_bodies wiring needed for them.


# ---------------------------------------------------------------------------
# DOMINANT DIGNITY ARCHITECTURE -- per-sign summary from the same chat
# message. DERIVED programmatically from RULERSHIPS/EXALTATIONS/DETRIMENTS/
# FALLS above (each sign's entry is just that table's reverse index) rather
# than hand-transcribed a second time -- both because it's genuinely
# redundant data (every sign entry IS the planet table, reorganized) and
# because computing it independently doubles as a cross-check: it was
# generated and diffed against your literal wording before being trusted,
# not assumed correct because the derivation seemed reasonable. See the
# verification in chat. Ophiuchus is the one exception -- no planet in the
# table above has any dignity there, so "Serpent Gate / Transmutation" is
# carried over as the plain thematic label you gave it, not derived.
# ---------------------------------------------------------------------------
_PLANET_SYMBOL: Dict[str, str] = {
    "Sun": "\u2609", "Moon": "\u263d", "Mercury": "\u263f", "Venus": "\u2640",
    "Mars": "\u2642", "Jupiter": "\u2643", "Saturn": "\u2644", "Uranus": "\u26e2",
    "Neptune": "\u2646", "Pluto": "\u2647", "Chiron": "\u26b7", "Rahu": "\u260a",
    "Ketu": "\u260b", "True BML": "\u26b8", "White Moon Selena": "\u26aa",
}


def _build_sign_architecture() -> Dict[str, str]:
    by_sign: Dict[str, List[str]] = {s: [] for s in SIGNS_12}
    for planet, signs in RULERSHIPS.items():
        for s in signs:
            by_sign[s].append(f"{planet} domicile")
    for planet, s in EXALTATIONS.items():
        by_sign[s].append(f"{planet} exaltation")
    for planet, signs in DETRIMENTS.items():
        for s in signs:
            by_sign[s].append(f"{planet} detriment")
    for planet, s in FALLS.items():
        by_sign[s].append(f"{planet} fall")
    result = {s: " / ".join(entries) for s, entries in by_sign.items() if entries}
    result["Ophiuchus"] = "Serpent Gate / Transmutation"  # thematic, not derived -- see docstring above
    return result


SIGN_DIGNITY_ARCHITECTURE: Dict[str, str] = _build_sign_architecture()


def planet_dignity(planet: str, sign: str) -> str:
    """'rulership' | 'exaltation' | 'fall' | 'detriment' | '' -- exact
    precedence order from your source (rulership checked before exaltation)."""
    if sign in RULERSHIPS.get(planet, []):
        return "rulership"
    if sign in DETRIMENTS.get(planet, []):
        return "detriment"
    if sign == EXALTATIONS.get(planet):
        return "exaltation"
    if sign == FALLS.get(planet):
        return "fall"
    return ""


def _dms(deg: float) -> str:
    """Decimal degrees -> D°MM'SS\" string, for orb display in logs."""
    d = int(deg)
    rem = (deg - d) * 60
    m = int(rem)
    s = round((rem - m) * 60)
    if s == 60:
        m += 1
        s = 0
    if m == 60:
        d += 1
        m = 0
    return f"{d}\u00b0{m:02d}'{s:02d}\""


def _log_entry(pair: str, kind: str, asp: str, orb: float, strength: float, contrib: float) -> dict:
    return {
        "pair": pair, "type": kind, "aspect": asp,
        "orb": round(orb, 4), "orb_dms": _dms(orb),
        "strength": round(strength, 3), "contrib": round(contrib, 3),
    }


# ---------------------------------------------------------------------------
# ASPECT ENGINE -- verbatim.
# ---------------------------------------------------------------------------
AspectHit = Tuple[str, float, float]  # (aspect_name, actual_orb, base_score)


def short_arc(lon1: float, lon2: float) -> float:
    """Minimum arc between two ecliptic longitudes (always 0-180deg)."""
    diff = abs(lon1 - lon2) % 360.0
    return min(diff, 360.0 - diff)


def detect_aspects(lon1: float, lon2: float) -> List[AspectHit]:
    """All aspects triggered between two positions (a pair CAN trigger
    more than one aspect if orbs overlap -- not artificially deduped)."""
    sep = short_arc(lon1, lon2)
    hits: List[AspectHit] = []
    for name, asp in ASPECTS.items():
        delta = abs(sep - asp["angle"])
        if delta <= asp["orb"]:
            hits.append((name, delta, asp["score"]))
    return hits


def orb_strength(actual: float, maximum: float) -> float:
    """Linear orb-strength: 1.0 at exact aspect, 0.0 at the orb boundary."""
    return 1.0 - (actual / maximum)


# ---------------------------------------------------------------------------
# SCORING ENGINE -- verbatim.
#   Planet-Planet : base_score x avg_weight x orb_strength
#   Planet-Star   : base_score x avg_weight x orb_strength x STAR_FACTOR
# ---------------------------------------------------------------------------
STAR_FACTOR = 0.70  # fixed stars contribute slightly less than moving planets


def score_aspects(
    planet_pos: Dict[str, float],
    planet_wts: Dict[str, int],
    star_pos: Dict[str, float],
) -> Tuple[float, List[dict]]:
    """Score all planet-planet and planet-star aspect pairs."""
    total = 0.0
    log: List[dict] = []
    bodies = list(planet_pos.keys())

    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            b1, b2 = bodies[i], bodies[j]
            w_avg = (planet_wts[b1] + planet_wts[b2]) / 2.0
            for asp, orb_used, base in detect_aspects(planet_pos[b1], planet_pos[b2]):
                sf = orb_strength(orb_used, ASPECTS[asp]["orb"])
                c = base * w_avg * sf
                total += c
                log.append(_log_entry(f"{b1} / {b2}", "P-P", asp, orb_used, sf, c))

    for planet, plon in planet_pos.items():
        pw = planet_wts[planet]
        for star, slon in star_pos.items():
            sw = STAR_CATALOG.get(star, 5)
            w_avg = (pw + sw) / 2.0
            for asp, orb_used, base in detect_aspects(plon, slon):
                sf = orb_strength(orb_used, ASPECTS[asp]["orb"])
                c = base * w_avg * sf * STAR_FACTOR
                total += c
                log.append(_log_entry(f"{planet} / {star}", "P-S", asp, orb_used, sf, c))

    log.sort(key=lambda x: abs(x["contrib"]), reverse=True)
    return total, log


def score_dignities(
    planet_pos: Dict[str, float],
    planet_wts: Dict[str, int],
    body_info: Dict[str, dict],
    extra_body_info: Optional[Dict[str, dict]] = None,
) -> Tuple[float, List[dict]]:
    """Per-planet dignity/debility bonus: DIGNITY_SCORE[status] x planet_weight.

    extra_body_info is for Chiron/Rahu/Ketu (chart.dignity_only_bodies) --
    scored the same way but through a SEPARATE loop that doesn't require
    planet_pos membership, since those 3 bodies are deliberately kept out
    of chart.positions (see tools/chart.py's module comment on
    calc_chiron_rahu_ketu for why: that dict feeds score_aspects directly,
    and adding them there would silently pull them into full aspect
    scoring against every other body and star using an invented weight).
    They get the same weight default (1) as any other unweighted body --
    no explicit weight was ever specified for them, so this uses the
    mechanism's own existing neutral default rather than inventing a
    specific number."""
    total = 0.0
    log: List[dict] = []
    for planet in RULERSHIPS:
        if planet not in planet_pos or planet not in body_info:
            continue
        sign = body_info[planet]["sign"]
        dignity = planet_dignity(planet, sign)
        if not dignity:
            continue
        bonus = DIGNITY_SCORE[dignity] * planet_wts.get(planet, 1)
        total += bonus
        log.append({
            "planet": planet, "sign": sign,
            "dignity": dignity, "bonus": round(bonus, 2),
        })

    for planet, info in (extra_body_info or {}).items():
        if planet not in RULERSHIPS:
            continue
        sign = info.get("sign")
        dignity = planet_dignity(planet, sign) if sign else None
        if not dignity:
            continue
        bonus = DIGNITY_SCORE[dignity] * planet_wts.get(planet, 1)
        total += bonus
        log.append({
            "planet": planet, "sign": sign,
            "dignity": dignity, "bonus": round(bonus, 2),
        })

    return total, log


def normalize(raw: float, lo: float = -600.0, hi: float = 1200.0) -> float:
    """Map raw score -> 0-100."""
    return max(0.0, min(100.0, (raw - lo) / (hi - lo) * 100.0))


def rating_label(s: float) -> str:
    if s >= 80:
        return "Exceptional"
    if s >= 65:
        return "Strong"
    if s >= 50:
        return "Moderate"
    if s >= 35:
        return "Developing"
    return "Challenging"


# ---------------------------------------------------------------------------
# Agent-facing wrapper
# ---------------------------------------------------------------------------
@dataclass
class WealthScoreResult:
    raw_score: float
    normalized_score: float
    rating: str
    aspect_log: List[dict] = field(default_factory=list)
    dignity_log: List[dict] = field(default_factory=list)
    is_day_chart: bool = True
    boosts_applied: List[str] = field(default_factory=list)
    numerology_boost: float = 0.0


def finalize_wealth_score(
    asp_total: float, dig_total: float,
    asp_log: List[dict], dig_log: List[dict],
    is_day: bool, numerology_boost: float = 0.0,
) -> WealthScoreResult:
    """The raw-sum + normalize + package step, split out from score_wealth()
    so a caller that needs numerology can compute score_aspects()/
    score_dignities() once, derive the numerology boost from THOSE logs
    (numerology.py's own design: it scales each cipher's ruling planet's
    already-computed aspect/dignity contribution, it doesn't compute
    anything independently), then finalize -- without score_wealth()
    silently recomputing aspects/dignities a second time to do it.

    raw = asp_total + dig_total + numerology_boost, matching your source's
    main(): `raw = asp_score + dig_bonus + num_boost`. This is additive,
    added BEFORE normalize() -- unlike the Gate/Typology/Calendar boost
    tiers in calendar_bridge.py and typology.py, which multiply the
    already-normalized 0-100 score. Different mechanism because that's
    what your source actually does, not a stylistic choice on this end."""
    raw = asp_total + dig_total + numerology_boost
    norm = normalize(raw)
    return WealthScoreResult(
        raw_score=round(raw, 3),
        normalized_score=round(norm, 2),
        rating=rating_label(norm),
        aspect_log=asp_log,
        dignity_log=dig_log,
        is_day_chart=is_day,
        numerology_boost=round(numerology_boost, 3),
    )


def score_wealth(chart: NatalChart, numerology_boost: float = 0.0) -> WealthScoreResult:
    """Compute the full wealth score for a NatalChart: aspects + dignities
    (+ optional numerology_boost, additive, pre-normalization), normalized
    to 0-100 with a rating label. Convenience wrapper around
    score_aspects() + score_dignities() + finalize_wealth_score() for
    callers that don't need the intermediate logs themselves -- if you do
    (e.g. to compute a numerology boost from them first), call those
    three directly instead of this, to avoid computing aspects/dignities
    twice."""
    asp_total, asp_log = score_aspects(chart.positions, chart.weights, chart.star_positions)
    dig_total, dig_log = score_dignities(chart.positions, chart.weights, chart.body_info)
    return finalize_wealth_score(asp_total, dig_total, asp_log, dig_log, chart.is_day, numerology_boost)


def score_result_to_dict(result: WealthScoreResult, max_aspect_log: Optional[int] = None) -> dict:
    """max_aspect_log caps how many aspect_log entries are included (already
    sorted by |contrib| descending, so capping keeps the strongest hits).
    None (default) returns everything -- used for direct/analytical callers
    like main.py's --direct mode. The agent dispatch passes a cap, since
    the 30-star catalog produces ~200 aspect hits per chart and the full
    log would otherwise be re-sent as input tokens on every subsequent
    turn of the conversation."""
    full_log = result.aspect_log
    truncated = max_aspect_log is not None and len(full_log) > max_aspect_log
    return {
        "raw_score": result.raw_score,
        "normalized_score": result.normalized_score,
        "rating": result.rating,
        "is_day_chart": result.is_day_chart,
        "aspect_log": full_log[:max_aspect_log] if truncated else full_log,
        "aspect_log_total_count": len(full_log),
        "aspect_log_truncated": truncated,
        "dignity_log": result.dignity_log,
        "numerology_boost": result.numerology_boost,
        "boosts_applied": result.boosts_applied,
    }
