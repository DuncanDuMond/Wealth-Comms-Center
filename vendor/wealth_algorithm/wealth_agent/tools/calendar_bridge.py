"""
calendar_bridge.py — Cosmic Playing Card Calendar <-> Wealth Score bridge.

PART 1 (cosmic_day_to_date_raw / date_to_cosmic_raw / get_card / MONTH_SEGMENTS
/ etc.) is a FAITHFUL PORT of your uploaded cosmic_calendar.py -- same
MONTH_SEGMENTS table (all 13 months, exact suit/day/card-index triples),
same is_greg_leap / cosmic_year_start / Feb-29 shift arithmetic / Joker Day
handling, same multi-candidate-year search in the reverse lookup. Verified
against your actual script's output for a full leap-year sweep (see the
test run in chat) -- not reconstructed from memory.

PART 2 (COSMIC_MONTH_RULERS, SUIT_PLANET_GROUPS, apply_cosmic_boosts) is
the wealth-score integration layer. This was NOT in either uploaded file
-- you mentioned earlier having built this in a separate merged script
that hasn't been uploaded here, so:
  - The +15% / +10% multiplicative boost VALUES match what you described
    building previously.
  - COSMIC_MONTH_RULERS is DERIVED (not guessed): for each cosmic month's
    Gregorian midpoint, I computed the actual sidereal sign via your real
    sign_sidereal_13() + ayanamsa, then looked up that sign's ruler in
    your real RULERSHIPS table. This is grounded in your two real scripts,
    just not something you wrote directly.
  - SUIT_PLANET_GROUPS (which planets "belong" to each suit's element) has
    NO grounding in anything you've shared -- flagged clearly below.
If you have the actual merged integration script, upload it and I'll
replace this part with your real table instead.

Internal cosmic-year variable `cy` matches your source exactly: cy is the
Gregorian year of the STARTING December 19, and the externally-displayed
"Cosmic Year" label is cy+1 (Cosmic Year 2026 = Dec 2025 - December 2026).
The agent-facing functions at the bottom take/return the LABEL form
(what a user would say), converting to/from cy internally.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# CARD SYSTEM -- verbatim.
# ---------------------------------------------------------------------------
CARD_VALUES: List[str] = ['K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2', 'A']


def _ci(value: str) -> int:
    return CARD_VALUES.index(value)


SUIT_SYMBOL: Dict[str, str] = {
    'spades': '\u2660', 'diamonds': '\u2666', 'clubs': '\u2663', 'hearts': '\u2665',
}
SUIT_NAME: Dict[str, str] = {v: k.capitalize() for k, v in SUIT_SYMBOL.items()}
SUIT_NAME['\u2605'] = 'Joker'

_S = SUIT_SYMBOL

# Each entry: (suit_symbol, start_day, end_day, card_start_index).
# Card for cosmic day d in segment = CARD_VALUES[card_start_index + (d - start_day)]
MONTH_SEGMENTS: List[List[Tuple[str, int, int, int]]] = [
    # Month I    Dec 19 - Jan 15
    [(_S['spades'], 1, 13, _ci('K')), (_S['diamonds'], 14, 26, _ci('K')), (_S['clubs'], 27, 28, _ci('K'))],
    # Month II   Jan 16 - Feb 12
    [(_S['spades'], 1, 11, _ci('J')), (_S['diamonds'], 12, 24, _ci('K')), (_S['clubs'], 25, 28, _ci('K'))],
    # Month III  Feb 13 - Mar 12  (Feb 29 -> 7 of Diamonds intercalary)
    [(_S['spades'], 1, 9, _ci('9')), (_S['diamonds'], 10, 22, _ci('K')), (_S['clubs'], 23, 28, _ci('K'))],
    # Month IV   Mar 13 - Apr 9
    [(_S['spades'], 1, 7, _ci('7')), (_S['diamonds'], 8, 20, _ci('K')), (_S['clubs'], 21, 28, _ci('K'))],
    # Month V    Apr 10 - May 7
    [(_S['spades'], 1, 5, _ci('5')), (_S['diamonds'], 6, 18, _ci('K')), (_S['clubs'], 19, 28, _ci('K'))],
    # Month VI   May 8 - Jun 4
    [(_S['spades'], 1, 3, _ci('3')), (_S['diamonds'], 4, 16, _ci('K')), (_S['clubs'], 17, 28, _ci('K'))],
    # Month VII  Jun 5 - Jul 2
    [(_S['spades'], 1, 1, _ci('A')), (_S['diamonds'], 2, 14, _ci('K')),
     (_S['clubs'], 15, 27, _ci('K')), (_S['hearts'], 28, 28, _ci('K'))],
    # Month VIII Jul 3 - Jul 30
    [(_S['diamonds'], 1, 12, _ci('Q')), (_S['clubs'], 13, 25, _ci('K')), (_S['hearts'], 26, 28, _ci('K'))],
    # Month IX   Jul 31 - Aug 27
    [(_S['diamonds'], 1, 10, _ci('10')), (_S['clubs'], 11, 23, _ci('K')), (_S['hearts'], 24, 28, _ci('K'))],
    # Month X    Aug 28 - Sep 24
    [(_S['diamonds'], 1, 8, _ci('8')), (_S['clubs'], 9, 21, _ci('K')), (_S['hearts'], 22, 28, _ci('K'))],
    # Month XI   Sep 25 - Oct 22
    [(_S['diamonds'], 1, 6, _ci('6')), (_S['clubs'], 7, 19, _ci('K')), (_S['hearts'], 20, 28, _ci('K'))],
    # Month XII  Oct 23 - Nov 19
    [(_S['diamonds'], 1, 4, _ci('4')), (_S['clubs'], 5, 17, _ci('K')), (_S['hearts'], 18, 28, _ci('K'))],
    # Month XIII Nov 20 - Dec 17
    [(_S['diamonds'], 1, 2, _ci('2')), (_S['clubs'], 3, 15, _ci('K')), (_S['hearts'], 16, 28, _ci('K'))],
]

ROMAN: List[str] = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII']

MONTH_RANGES: List[str] = [
    'Dec 19 - Jan 15', 'Jan 16 - Feb 12', 'Feb 13 - Mar 12', 'Mar 13 - Apr 9',
    'Apr 10 - May 7', 'May 8 - Jun 4', 'Jun 5 - Jul 2', 'Jul 3 - Jul 30',
    'Jul 31 - Aug 27', 'Aug 28 - Sep 24', 'Sep 25 - Oct 22', 'Oct 23 - Nov 19',
    'Nov 20 - Dec 17',
]


# ---------------------------------------------------------------------------
# CORE LOGIC -- verbatim.
# ---------------------------------------------------------------------------
def is_greg_leap(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def cosmic_year_start(cy: int) -> date:
    """December 19 of cosmic year cy (the first day of that year)."""
    return date(cy, 12, 19)


def cosmic_day_to_date_raw(cy: int, month: int, day: int) -> date:
    """Cosmic (cy, month, day) -> Gregorian date. Feb 29 sits outside the
    364-day structure; any raw result on/after Feb 29 (of cy+1) shifts
    forward one day so months stay anchored to the same Gregorian range
    regardless of leap year."""
    d = cosmic_year_start(cy) + timedelta(days=(month - 1) * 28 + (day - 1))
    if is_greg_leap(cy + 1):
        feb29 = date(cy + 1, 2, 29)
        if d >= feb29:
            d += timedelta(days=1)
    return d


def leap_day_date(cy: int) -> date:
    """The Leap/Joker Day (December 18, cy+1) for cosmic year cy."""
    return date(cy + 1, 12, 18)


def get_card(month: int, day: int) -> Tuple[str, str]:
    """(suit_symbol, card_value) for a cosmic month/day -- pure table lookup."""
    for (suit, start, end, c_idx) in MONTH_SEGMENTS[month - 1]:
        if start <= day <= end:
            return (suit, CARD_VALUES[c_idx + (day - start)])
    raise ValueError(f"No card found for month={month}, day={day}")


def date_to_cosmic_raw(d: date) -> Optional[dict]:
    """Gregorian date -> cosmic position. Returns a dict with type
    'regular' | 'feb29' | 'leap_day', or None if unresolvable. Tries
    cy = d.year-1, d.year, d.year+1 in turn (your exact search order)."""
    for cy_offset in (-1, 0, 1):
        cy = d.year + cy_offset
        start = cosmic_year_start(cy)

        if d == leap_day_date(cy):
            return {'type': 'leap_day', 'cy': cy, 'card': ('\u2605', 'Joker'), 'greg': d}

        if is_greg_leap(cy + 1):
            feb29 = date(cy + 1, 2, 29)
            if d == feb29:
                return {'type': 'feb29', 'cy': cy, 'month': 3, 'day': 17,
                        'card': ('\u2666', '7'), 'greg': d}
            diff = (d - start).days
            if d > feb29:
                diff -= 1
        else:
            diff = (d - start).days

        if 0 <= diff < 364:
            month = diff // 28 + 1
            day = diff % 28 + 1
            return {'type': 'regular', 'cy': cy, 'month': month, 'day': day,
                    'card': get_card(month, day), 'greg': d}

    return None


def fmt_cosmic_year(cy: int) -> str:
    """Cosmic Year {cy+1} (Dec {cy} - December {cy+1})."""
    return f"Cosmic Year {cy + 1} (Dec {cy} - December {cy + 1})"


def card_str(card: Tuple[str, str]) -> str:
    """(suit, value) -> readable string, e.g. ('\\u2666','7') -> '7 of Diamonds'."""
    suit, value = card
    if suit == '\u2605':
        return "Joker"
    return f"{value} of {SUIT_NAME.get(suit, suit)}"


# ---------------------------------------------------------------------------
# PART 2: WEALTH-SCORE INTEGRATION LAYER (best-effort scaffolding -- see
# module docstring for what's grounded vs. invented).
# ---------------------------------------------------------------------------
BOOST_MONTH_RULER = 1.15   # matches what you described building previously
BOOST_SUIT_ELEMENT = 1.10  # matches what you described building previously
BOOST_DAY_GATE = 1.15      # new tier -- see apply_cosmic_boosts() and
                           # gate_calendar_bridge.py's day_gate(). Matches
                           # the month-ruler tier's size: landing on the
                           # Sun's one current Gate out of 64 is a tighter
                           # target than either existing category.

# DERIVED from your real sign_sidereal_13() + RULERSHIPS, evaluated at each
# cosmic month's Gregorian midpoint (mid-2026 ayanamsa as reference --
# ayanamsa drifts <0.02deg/year so this is stable at day-level precision
# for practical purposes). Two months can share a ruler since 28-day
# cosmic months don't align exactly with ~30-day sidereal signs -- that's
# a real consequence of the two systems, not an error.
# Note: Aquarius and Pisces each have two rulers in your RULERSHIPS table
# (Saturn/Uranus and Jupiter/Neptune respectively). The reverse sign->ruler
# map here took the LAST match by dict order, giving the modern ruler
# (Uranus, Neptune) -- an artifact of how I built the lookup, not a
# deliberate traditional-vs-modern choice. Swap to Saturn/Jupiter if you'd
# rather use the traditional rulers for those two months.
# Month XIII (Ophiuchus) has no ruler that can trigger the boost below:
# Chiron isn't a tracked/scored body in wealth_algorithm.py, only a label
# for Ophiuchus in a comment. Left as documented-but-structurally-inactive
# rather than fabricating a Chiron position that isn't in your source.
COSMIC_MONTH_RULERS: Dict[int, Tuple[str, str]] = {
    1:  ("Sagittarius", "Jupiter"),
    2:  ("Capricorn",   "Saturn"),
    3:  ("Aquarius",    "Uranus"),
    4:  ("Pisces",      "Neptune"),
    5:  ("Aries",       "Mars"),
    6:  ("Taurus",      "Venus"),
    7:  ("Taurus",      "Venus"),
    8:  ("Gemini",      "Mercury"),
    9:  ("Leo",         "Sun"),
    10: ("Leo",         "Sun"),
    11: ("Virgo",       "Venus"),    # custom rulership
    12: ("Libra",       "Mercury"),  # custom rulership
    13: ("Ophiuchus",   "Chiron"),   # label only -- see note above
}

# NOT grounded in either uploaded script -- pure scaffolding. Common
# Tarot-suit/element correspondence (Clubs=Wands=Fire, Diamonds=Pentacles
# =Earth, Spades=Swords=Air, Hearts=Cups=Water), mapped to the planets
# classically associated with each element. Replace freely.
SUIT_PLANET_GROUPS: Dict[str, dict] = {
    SUIT_SYMBOL['clubs']:    {"element": "Fire",  "planets": {"Sun", "Mars", "Jupiter"}},
    SUIT_SYMBOL['diamonds']: {"element": "Earth", "planets": {"Venus", "Saturn"}},
    SUIT_SYMBOL['spades']:   {"element": "Air",   "planets": {"Mercury", "Uranus"}},
    SUIT_SYMBOL['hearts']:   {"element": "Water", "planets": {"Moon", "Neptune", "Pluto", "True BML"}},
}


def apply_cosmic_boosts(
    score_dict: dict,
    cosmic_info: dict,
    gate_info: Optional[Dict[str, dict]] = None,
    day_gate: Optional[int] = None,
) -> dict:
    """Apply month-ruler, suit-element, and (optionally) day-gate boosts to
    a score_wealth() result (as produced by scoring.score_result_to_dict).
    Operates on the normalized 0-100 score, not the raw pre-normalization
    score -- most charts clamp to 100 on the raw scale, so boosting there
    would rarely be visible; boosting the normalized score keeps it
    meaningful. Returns a new dict; does not mutate the input.

    gate_info / day_gate are both optional and both None by default, so
    existing callers that don't compute Gates see no behavior change at
    all. To enable the day-gate tier, pass:
      gate_info = human_design_gates.bodies_to_gates(lons)   # this chart's Gates
      day_gate  = gate_calendar_bridge.day_gate(greg_date)["gate"]  # today's Sun-Gate
    Deliberately NOT imported here -- calendar_bridge.py stays free of any
    astrology-module dependency; the caller supplies already-computed data,
    same as it already does for score_dict and cosmic_info.
    """
    result = dict(score_dict)
    boosts_applied = list(result.get("boosts_applied", []))
    boosted_score = result["normalized_score"]

    bodies_involved = set()
    for e in result.get("aspect_log", []):
        bodies_involved.update(p.strip() for p in e["pair"].split(" / "))
    for e in result.get("dignity_log", []):
        bodies_involved.add(e["planet"])

    month = cosmic_info.get("month")
    if month and month in COSMIC_MONTH_RULERS:
        _sign, ruler = COSMIC_MONTH_RULERS[month]
        if ruler in bodies_involved:
            boosted_score *= BOOST_MONTH_RULER
            boosts_applied.append(f"month ruler boost ({ruler}, x{BOOST_MONTH_RULER})")

    card = cosmic_info.get("card")
    if card:
        suit_symbol = card[0]
        suit_info = SUIT_PLANET_GROUPS.get(suit_symbol)
        if suit_info and bodies_involved & suit_info["planets"]:
            boosted_score *= BOOST_SUIT_ELEMENT
            boosts_applied.append(
                f"suit element boost ({suit_info['element']}, x{BOOST_SUIT_ELEMENT})"
            )

    if gate_info and day_gate is not None:
        matching = sorted(
            b for b, g in gate_info.items()
            if g["gate"] == day_gate and b in bodies_involved
        )
        if matching:
            boosted_score *= BOOST_DAY_GATE
            boosts_applied.append(
                f"day gate boost ({', '.join(matching)}, Gate {day_gate}, x{BOOST_DAY_GATE})"
            )

    result["normalized_score"] = round(min(boosted_score, 100.0), 2)
    result["boosts_applied"] = boosts_applied
    result["cosmic_day_info"] = cosmic_info
    return result


# ---------------------------------------------------------------------------
# Agent-facing wrappers -- LABEL-based (cosmic_year = cy+1, what a person
# would actually say), converting to/from your internal cy representation.
# ---------------------------------------------------------------------------
def cosmic_day_to_date(cosmic_year_label: int, month: int, day_in_month: int) -> dict:
    """Forward lookup: cosmic (year LABEL, month, day) -> Gregorian date +
    card. Returns an explicit error dict (never raises) on bad input."""
    if not (1 <= month <= 13):
        return {"error": f"month must be 1-13, got {month}"}
    if not (1 <= day_in_month <= 28):
        return {"error": f"day_in_month must be 1-28, got {day_in_month}"}

    cy = cosmic_year_label - 1
    d = cosmic_day_to_date_raw(cy, month, day_in_month)
    suit, value = get_card(month, day_in_month)
    sign, ruler = COSMIC_MONTH_RULERS.get(month, (None, None))

    return {
        "gregorian_date": d.isoformat(),
        "cosmic_year_label": cosmic_year_label,
        "cosmic_year_display": fmt_cosmic_year(cy),
        "month": month,
        "month_roman": ROMAN[month - 1],
        "month_range": MONTH_RANGES[month - 1],
        "month_sign": sign,
        "day_in_month": day_in_month,
        "card": (suit, value),
        "card_display": card_str((suit, value)),
    }


def date_to_cosmic_day(gregorian_date: str) -> dict:
    """Reverse lookup: Gregorian date -> cosmic year LABEL/month/day + card.
    Handles Joker Day and intercalary Feb 29 as explicit cases, matching
    your source's three result types."""
    y, m, d = (int(p) for p in gregorian_date.split("-"))
    result = date_to_cosmic_raw(date(y, m, d))
    if result is None:
        return {"error": f"{gregorian_date} could not be resolved to a cosmic date"}

    cy = result["cy"]
    label = cy + 1
    base = {
        "gregorian_date": gregorian_date,
        "cosmic_year_label": label,
        "cosmic_year_display": fmt_cosmic_year(cy),
        "card": result["card"],
        "card_display": card_str(result["card"]),
    }

    if result["type"] == "leap_day":
        base.update({"is_joker_day": True, "is_intercalary": False,
                      "month": None, "month_sign": None, "day_in_month": None,
                      "note": "Leap/Joker Day -- outside the month structure."})
    elif result["type"] == "feb29":
        base.update({"is_joker_day": False, "is_intercalary": True,
                      "month": 3, "month_sign": COSMIC_MONTH_RULERS[3][0],
                      "day_in_month": 17,
                      "note": "Intercalary Feb 29, placed between Month III days 16 and 17."})
    else:
        month = result["month"]
        sign, _ruler = COSMIC_MONTH_RULERS.get(month, (None, None))
        base.update({"is_joker_day": False, "is_intercalary": False,
                      "month": month, "month_roman": ROMAN[month - 1],
                      "month_range": MONTH_RANGES[month - 1],
                      "month_sign": sign, "day_in_month": result["day"]})

    return base
