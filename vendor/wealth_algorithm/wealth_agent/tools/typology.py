"""
typology.py — Enneagram + MBTI overlay on the rebased 13-constellation wheel.

SOURCE: two AI-generated reference images ("Enneagram Wheel - Rebased IAU
Zodiac" and "The 13-Constellation MBTI Model"), plus typed correspondence
tables. Read carefully, field by field, against both images directly
(not just the typed tables) -- and the two images disagree with each
other and with the typed tables in several places. See the top-level
chat response for the specific discrepancies found. This module documents
inline, per-field, which source each value came from and how confident
that source is.

BOUNDARY TABLE: an INDEPENDENT third ring, not the same data as
_13SIGN_TROP in chart.py or the Gate wheel in human_design_gates.py.
Sagittarius = 0 sidereal degrees here (vs. Aries = 0 for _13SIGN_TROP's
underlying IAU-crossing data, before ayanamsa shift). Verified as a clean,
gap-free 0-360 partition (13 widths sum to exactly 360.0) before use --
but the DEGREE VALUES THEMSELVES come from an AI-generated image, not a
computed/verified astronomical source like everything else in this
project. Treat them as design intent, not measured precision, until
double-checked against whatever tool actually generated them.

Applied directly to sidereal longitude with NO further ayanamsa
correction -- the source images don't mention ayanamsa at all, unlike
_13SIGN_TROP which explicitly stores tropical degrees requiring a
per-date shift. If that's wrong (i.e. if these were meant to also be
ayanamsa-shifted), the fix is localized to sign_archetype_wheel() below.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# REBASED WHEEL BOUNDARIES -- from the MBTI image's own numbered table,
# used as the authoritative source since it's internally self-consistent
# (its outer-ring labels agree with its own numbered list) and the
# Enneagram image's labels in the Libra/Scorpio region are not.
# ---------------------------------------------------------------------------
ARCHETYPE_WHEEL_BOUNDARIES: List[Tuple[str, float]] = [
    ("Sagittarius",   0.0),
    ("Capricorn",    33.4859),
    ("Aquarius",     59.0617),
    ("Pisces",       82.2285),
    ("Aries",       124.2182),
    ("Taurus",      143.9468),
    ("Gemini",      180.8057),
    ("Cancer",      210.2594),
    ("Leo",         227.4082),
    ("Virgo",       265.8247),
    ("Libra",       315.5382),
    ("Scorpio",     334.4154),
    ("Ophiuchus",   347.6427),
]


def sign_archetype_wheel(sid_lon: float) -> str:
    """Sidereal longitude -> constellation name on the REBASED (Sagittarius
    = 0) wheel. Independent of sign_sidereal_13() in chart.py -- the two
    wheels don't share boundary edges, by design (see module docstring)."""
    sid_lon = sid_lon % 360.0
    result = ARCHETYPE_WHEEL_BOUNDARIES[-1][0]  # Ophiuchus wraps to 360
    for name, start in ARCHETYPE_WHEEL_BOUNDARIES:
        if sid_lon >= start:
            result = name
        else:
            break
    return result


def bodies_to_archetype_wheel(sid_lons: Dict[str, float]) -> Dict[str, str]:
    """{body: sidereal_longitude} -> {body: rebased-wheel constellation}."""
    return {name: sign_archetype_wheel(lon) for name, lon in sid_lons.items()}


# ---------------------------------------------------------------------------
# ENNEAGRAM -- "core type" table (HIGH CONFIDENCE: typed directly by you,
# no image-transcription risk). Used for the actual resonance/boost check
# below. planets / constellations are lists since several types list more
# than one of each.
# ---------------------------------------------------------------------------
ENNEAGRAM_CORE: Dict[int, dict] = {
    1: {"archetype": "Reformer",      "planets": ["Saturn"],         "constellations": ["Capricorn", "Virgo"]},
    2: {"archetype": "Helper",        "planets": ["Venus"],          "constellations": ["Taurus", "Virgo"]},
    3: {"archetype": "Achiever",      "planets": ["Sun"],            "constellations": ["Leo"]},
    4: {"archetype": "Individualist", "planets": ["Moon"],           "constellations": ["Cancer", "Pisces"]},
    5: {"archetype": "Investigator",  "planets": ["Mercury"],        "constellations": ["Gemini", "Libra"]},
    6: {"archetype": "Loyalist",      "planets": ["Saturn"],         "constellations": ["Capricorn", "Aquarius"]},
    7: {"archetype": "Enthusiast",    "planets": ["Jupiter"],        "constellations": ["Sagittarius", "Pisces"]},
    8: {"archetype": "Challenger",    "planets": ["Mars", "Pluto"],  "constellations": ["Aries", "Scorpio"]},
    9: {"archetype": "Peacemaker",    "planets": ["Neptune"],        "constellations": ["Pisces", "Ophiuchus"]},
}

# ---------------------------------------------------------------------------
# ENNEAGRAM -- full 13-sector wheel positional table (MEDIUM CONFIDENCE:
# read directly off the Enneagram wheel image, sector by sector, cross-
# checked against the MBTI image's boundary table where the Enneagram
# image's own labels were wrong -- see module docstring). "type" is a
# string, not always a plain int: Virgo's is "2/1" as literally labeled.
# Scorpio has no visible entry in the wheel image at all (see docstring);
# filled from your separately-typed cycle sequence ("Scorpio -- 8")
# instead, flagged via source="cycle_text_gap_fill".
# ---------------------------------------------------------------------------
ENNEAGRAM_BY_CONSTELLATION: Dict[str, dict] = {
    "Sagittarius": {"type": "7",   "archetype": "Enthusiast",              "planet": "Jupiter",       "element": "Fire",  "source": "wheel_image"},
    "Capricorn":   {"type": "1",   "archetype": "Reformer",                "planet": "Saturn",        "element": "Earth", "source": "wheel_image"},
    "Aquarius":    {"type": "6",   "archetype": "Loyalist",                "planet": "Saturn",        "element": "Air",   "source": "wheel_image"},
    "Pisces":      {"type": "9",   "archetype": "Peacemaker",              "planet": "Neptune",       "element": "Water", "source": "wheel_image"},
    "Aries":       {"type": "8",   "archetype": "Challenger",              "planet": "Mars",          "element": "Fire",  "source": "wheel_image"},
    "Taurus":      {"type": "2",   "archetype": "Helper",                  "planet": "Venus",         "element": "Earth", "source": "wheel_image"},
    "Gemini":      {"type": "5",   "archetype": "Investigator",            "planet": "Mercury",       "element": "Air",   "source": "wheel_image"},
    "Cancer":      {"type": "4",   "archetype": "Individualist",           "planet": "Moon",          "element": "Water", "source": "wheel_image"},
    "Leo":         {"type": "3",   "archetype": "Achiever",                "planet": "Sun",           "element": "Fire",  "source": "wheel_image"},
    "Virgo":       {"type": "2/1", "archetype": "Refiner (Helper/Reformer)", "planet": "Venus",       "element": "Earth", "source": "wheel_image"},
    "Libra":       {"type": "5",   "archetype": "Analyst",                 "planet": "Mercury",       "element": "Air",   "source": "wheel_image_relabeled"},  # image says "Scorpius" here -- corrected, see docstring
    "Scorpio":     {"type": "8",   "archetype": "Challenger",              "planet": "Mars/Pluto",    "element": None,    "source": "cycle_text_gap_fill"},     # not shown in wheel image at all
    "Ophiuchus":   {"type": "9",   "archetype": "Alchemist",               "planet": "Neptune",       "element": "Spirit", "source": "wheel_image"},
}

# Narrative-only "cycle of consciousness" journey text, as you typed it.
# NOT reconciled 1:1 with ENNEAGRAM_BY_CONSTELLATION above -- the two
# don't fully agree with each other either (e.g. this groups "1/6" at
# Capricorn, the wheel image keeps them as separate Capricorn=1 /
# Aquarius=6 sectors). Keep this for interpretive/explanatory text, not
# as a computational source.
ENNEAGRAM_CYCLE_NARRATIVE: List[Tuple[str, str]] = [
    ("Sagittarius", "7"), ("Capricorn", "1/6"), ("Aquarius", "5/6"),
    ("Pisces", "9/7"), ("Aries", "8"), ("Taurus", "2"), ("Gemini", "5"),
    ("Cancer", "4"), ("Leo", "3"), ("Virgo", "2/1"), ("Libra", "5"),
    ("Scorpio", "8"), ("Ophiuchus", "9/8"),
]


# ---------------------------------------------------------------------------
# MBTI -- by constellation (MEDIUM CONFIDENCE: read directly off the MBTI
# image, sector by sector; archetype names filled in from your typed
# table only where a (code, constellation) pair matches exactly -- left
# None where the image shows a code/constellation combination your typed
# table didn't cover). All 16 real MBTI types are represented somewhere
# in this table; the typed table alone was missing ESFJ entirely.
# ---------------------------------------------------------------------------
MBTI_BY_CONSTELLATION: Dict[str, dict] = {
    "Sagittarius": {"ruler": "Jupiter",                    "codes": {"ENFP": "Visionary Explorer", "ENFJ": "Inspirational Guide"}},
    "Capricorn":   {"ruler": "Saturn",                     "codes": {"INTJ": "Architect", "ISTJ": "Logistician", "ESTJ": "Executive"}},
    "Aquarius":    {"ruler": "Uranus (Saturn co-ruler)",   "codes": {"ENTP": "Innovator", "INTP": "Systems Analyst"}},
    "Pisces":      {"ruler": "Neptune (Jupiter co-ruler)", "codes": {"INFJ": "Visionary", "INFP": "Idealist"}},
    "Aries":       {"ruler": "Mars",                       "codes": {"ENTJ": "Commander", "ESTP": "Entrepreneur"}},
    "Taurus":      {"ruler": "Venus",                      "codes": {"ISFP": "Artist", "ESFJ": None}},
    "Gemini":      {"ruler": "Mercury",                    "codes": {"ENTP": None, "ISTP": None}},
    "Cancer":      {"ruler": "Moon",                       "codes": {"ISFJ": "Guardian", "ESFJ": None}},
    "Leo":         {"ruler": "Sun",                        "codes": {"ESFP": "Entertainer", "ENFJ": None}},
    "Virgo":       {"ruler": "Venus (custom rulership)",   "codes": {"INFP": "Refiner", "ISTJ": None}},
    "Libra":       {"ruler": "Mercury (custom rulership)", "codes": {"INTP": "Integrator", "ENFJ": None}},
    "Scorpio":     {"ruler": "Pluto (Mars co-ruler)",      "codes": {"INTJ": None, "INFJ": None}},
    "Ophiuchus":   {"ruler": "Mercury, Pluto, Chiron",     "codes": {"INTJ": "Alchemist", "INFJ": None}},
}

# Derived reverse index: {mbti_code: [(constellation, archetype_or_None), ...]}
# Built from MBTI_BY_CONSTELLATION so it can't drift out of sync with it.
MBTI_CONSTELLATIONS: Dict[str, List[Tuple[str, Optional[str]]]] = {}
for _const, _data in MBTI_BY_CONSTELLATION.items():
    for _code, _archetype in _data["codes"].items():
        MBTI_CONSTELLATIONS.setdefault(_code, []).append((_const, _archetype))

VALID_MBTI_CODES = frozenset(MBTI_CONSTELLATIONS.keys())
assert len(VALID_MBTI_CODES) == 16, f"expected all 16 MBTI types, got {len(VALID_MBTI_CODES)}"


# ---------------------------------------------------------------------------
# INPUT PARSING -- from your chat message, not any uploaded script. Accepts
# the raw string a person types (e.g. from the new startup prompt) and
# splits it into the CORE value (already used everywhere in this module's
# scoring) plus an optional wing/variant, which is new, descriptive-only
# data: no ruling-planet-style resonance mechanic was specified for wing
# or A/T, so none is invented here -- they're carried through for display,
# not scored. Enneagram wing must be numerically adjacent to the core type
# (standard Enneagram convention: type 7 can only wing to 6 or 8, wrapping
# 9<->1) -- checked here rather than silently accepted, since an
# impossible wing combination is much more likely a typo than an
# intentional unconventional claim.
# ---------------------------------------------------------------------------
def parse_enneagram_input(raw: str) -> Tuple[Optional[int], Optional[int]]:
    """'7w8' -> (7, 8); '9' -> (9, None); 'N/A' (case-insensitive, or
    blank) -> (None, None). Raises ValueError on anything else malformed."""
    raw = raw.strip()
    if raw == "" or raw.upper() in ("N/A", "NA", "UNKNOWN"):
        return None, None

    if "w" in raw.lower():
        core_str, wing_str = raw.lower().split("w", 1)
        try:
            core, wing = int(core_str), int(wing_str)
        except ValueError:
            raise ValueError(f"'{raw}' isn't a valid Enneagram type -- expected XwX (e.g. '7w8'), a plain number, or N/A")
        if not (1 <= core <= 9) or not (1 <= wing <= 9):
            raise ValueError(f"Enneagram type and wing must each be 1-9, got '{raw}'")
        if wing not in ((core % 9) + 1, ((core - 2) % 9) + 1):
            raise ValueError(
                f"'{raw}': a wing must be numerically adjacent to the core type "
                f"(type {core} can only wing to {((core - 2) % 9) + 1} or {(core % 9) + 1})"
            )
        return core, wing

    try:
        core = int(raw)
    except ValueError:
        raise ValueError(f"'{raw}' isn't a valid Enneagram type -- expected XwX (e.g. '7w8'), a plain number, or N/A")
    if not (1 <= core <= 9):
        raise ValueError(f"Enneagram type must be 1-9, got '{raw}'")
    return core, None


def parse_mbti_input(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """'INTJ-A' -> ('INTJ', 'A'); 'INTJ-T' -> ('INTJ', 'T'); 'INTJ' ->
    ('INTJ', None); 'N/A' (case-insensitive, or blank) -> (None, None).
    Raises ValueError on anything else malformed."""
    raw = raw.strip().upper()
    if raw == "" or raw in ("N/A", "NA", "UNKNOWN"):
        return None, None

    if "-" in raw:
        code, variant = raw.split("-", 1)
        if variant not in ("A", "T"):
            raise ValueError(f"'{raw}': the suffix after '-' must be A (Assertive) or T (Turbulent)")
    else:
        code, variant = raw, None

    if code not in VALID_MBTI_CODES:
        raise ValueError(f"'{code}' isn't a real 4-letter MBTI code")
    return code, variant


# ---------------------------------------------------------------------------
# RESONANCE -- ported concept from the Gate/month-ruler boost pattern
# already in this project, applied here for the first time to GIVEN
# (self-reported) rather than computed data. Uses ENNEAGRAM_CORE /
# MBTI_CONSTELLATIONS (the higher-confidence tables) rather than the
# wheel-image-derived per-sector tables, which carry more transcription
# risk -- see module docstring.
# ---------------------------------------------------------------------------
BOOST_TYPOLOGY_PLANET = 1.15   # given type's ruling planet is active in the chart
BOOST_TYPOLOGY_FIELD = 1.10    # a tracked body sits in one of the type's constellations


def typology_resonance(
    enneagram_type: Optional[int],
    mbti_type: Optional[str],
    bodies_involved: set,
    body_constellations: Dict[str, str],
) -> Tuple[List[str], List[str]]:
    """Check a given Enneagram type / MBTI code against a chart's active
    bodies (bodies_involved, e.g. from aspect_log/dignity_log) and each
    body's placement on the rebased wheel (body_constellations, e.g. from
    bodies_to_archetype_wheel()). Returns (planet_matches, field_matches)
    as lists of human-readable descriptions -- empty lists mean no
    resonance found, not an error."""
    planet_matches: List[str] = []
    field_matches: List[str] = []

    if enneagram_type is not None and enneagram_type in ENNEAGRAM_CORE:
        core = ENNEAGRAM_CORE[enneagram_type]
        for planet in core["planets"]:
            if planet in bodies_involved:
                planet_matches.append(f"Enneagram {enneagram_type} ({core['archetype']}) ruling planet {planet}")
        for body, constellation in body_constellations.items():
            if constellation in core["constellations"]:
                field_matches.append(f"Enneagram {enneagram_type} field {constellation} ({body})")

    if mbti_type:
        code = mbti_type.strip().upper()
        for constellation, _archetype in MBTI_CONSTELLATIONS.get(code, []):
            ruler = MBTI_BY_CONSTELLATION[constellation]["ruler"]
            # ruler strings can carry parentheticals ("Uranus (Saturn co-ruler)");
            # match on the first token only.
            ruler_planet = ruler.split(" ")[0].rstrip(",")
            if ruler_planet in bodies_involved:
                planet_matches.append(f"MBTI {code} ruling planet {ruler_planet} ({constellation})")
            for body, body_const in body_constellations.items():
                if body_const == constellation:
                    field_matches.append(f"MBTI {code} field {constellation} ({body})")

    return planet_matches, field_matches


def apply_typology_boost(
    score_dict: dict,
    enneagram_type: Optional[int],
    mbti_type: Optional[str],
    bodies_involved: set,
    body_constellations: Dict[str, str],
) -> dict:
    """Apply the typology resonance boost to a score dict (as produced by
    calendar_bridge.apply_cosmic_boosts / apply_all_cosmic_boosts, or
    directly to scoring.score_result_to_dict's output). Composable with
    those -- call this after them, or before; order doesn't matter since
    each boost multiplies the current normalized_score independently.
    Returns a new dict; does not mutate the input."""
    result = dict(score_dict)
    boosts_applied = list(result.get("boosts_applied", []))
    boosted_score = result["normalized_score"]

    planet_matches, field_matches = typology_resonance(
        enneagram_type, mbti_type, bodies_involved, body_constellations
    )

    if planet_matches:
        boosted_score *= BOOST_TYPOLOGY_PLANET
        boosts_applied.append(
            f"typology planet boost ({'; '.join(planet_matches)}, x{BOOST_TYPOLOGY_PLANET})"
        )
    if field_matches:
        boosted_score *= BOOST_TYPOLOGY_FIELD
        boosts_applied.append(
            f"typology field boost ({'; '.join(field_matches)}, x{BOOST_TYPOLOGY_FIELD})"
        )

    result["normalized_score"] = round(min(boosted_score, 100.0), 2)
    result["boosts_applied"] = boosts_applied
    return result
