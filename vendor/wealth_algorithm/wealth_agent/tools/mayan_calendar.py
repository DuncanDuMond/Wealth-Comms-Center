"""
mayan_calendar.py — 260-day Tzolkin calendar: Day Sign, Galactic Tone,
Trecena, Kin number, and a constructed "Tree of Life" overlay.

Mirrors calendar_bridge.py's forward/reverse date-function pattern, but
the two calendars have a structural difference worth understanding before
reading further: the Cosmic Calendar has an absolute epoch (Dec 19 of a
specific year) and a "Cosmic Year" label, so a (year, month, day) triple
names exactly one Gregorian date. The Tzolkin has no such absolute epoch
in ordinary use -- it's a 260-day cycle that has repeated continuously
for millennia with no "year" attached, so a given (day sign, tone) pair
recurs every 260 days forever. There's no single reverse-lookup answer;
tzolkin_occurrences_near() below returns the nearest matches instead.

CORRELATION: this module uses the Goodman-Martinez-Thompson (GMT)
correlation constant, Julian Day Number 584283 -- the standard used by
the overwhelming majority of Mayanist scholars and by every contemporary
Tzolkin calculator checked while building this (including the one you
linked, mayan.org, and academic sources cross-referencing colonial-period
documents with carved monument dates). VERIFIED, not assumed: this
module's forward date function correctly reproduces two independently-
documented reference points --
  - August 11, 3114 BCE (proleptic Gregorian) = 4 Ajaw (the Long Count
    creation date, JDN 584283 by definition of the correlation constant)
  - December 21, 2012 = 4 Ajaw (Long Count 13.0.0.0.0 -- the "end of the
    13th baktun" date, widely reported at the time and confirmed here
    against the Smithsonian's own Maya calendar glossary and multiple
    independent scholarly sources)
See the test run in chat for both checks.

TREE OF LIFE: the source page (mymayansign.com/mayan-sign-calculator/)
describes the CONCEPT -- "your Day Sign sits at the center, with a day
sign in each of the four directions: your past behind, your future
ahead, your masculine power on one side and your feminine on the other...
the complete Tree of Life opens into nine" -- but does not disclose the
actual formula for which four (or nine) day signs those are, and
searching further didn't turn it up either. tree_of_life() below
therefore implements a CONSTRUCTED interpretation, not a verified port:
  - Past  = 1 trecena (13 days) before the center date
  - Future = 1 trecena (13 days) after the center date
  - Masculine = 4 days before center
  - Feminine  = 4 days after center
This is symmetric and mechanically simple, which is the most defensible
thing about it -- it is NOT verified against this site's or any other
site's actual method. The offsets are named constants right below this
docstring specifically so they're easy to replace if you find or specify
the real formula. The stated "opens into nine" is NOT implemented at
all -- going from 5 to 9 positions with no textual basis for what the
other 4 represent would mean inventing content, not constructing a
reasonable interpretation of something described. If you have the actual
rule (or want to define one), the extra 4 slots are a straightforward
addition once that exists.

NIGHT LORD: a 9-day cycle (the "Nine Lords of the Night" / Bolontiku) is
a real, separately-documented Mesoamerican calendrical concept, distinct
from the Tzolkin's 13/20 structure, and mymayansign.com's own homepage
copy mentions "Night Lord" as part of a fuller reading. Included as a
simple numbered 1-9 cycle. The specific epoch used to number "Lord 1" is
NOT independently verified against mymayansign.com specifically -- flagged
in the function docstring below.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import swisseph as swe

# ---------------------------------------------------------------------------
# CORRELATION CONSTANT -- see module docstring for verification.
# ---------------------------------------------------------------------------
GMT_CORRELATION_JDN = 584283  # 0.0.0.0.0 4 Ajaw 8 Kumk'u = Aug 11, 3114 BCE

# ---------------------------------------------------------------------------
# 20 DAY SIGNS (Nawales) -- traditional Yucatec order. keyword is a short,
# commonly-cited traditional association, kept brief and not attributed to
# any specific site's exact wording.
# ---------------------------------------------------------------------------
DAY_SIGNS: List[Tuple[str, str, str]] = [
    ("Imix",     "Crocodile", "primal waters, new beginnings"),
    ("Ik'",      "Wind",      "breath, spirit, communication"),
    ("Ak'b'al",  "Night",     "darkness, dreams, the inner world"),
    ("K'an",     "Seed",      "growth, potential, ripening"),
    ("Chikchan", "Serpent",   "life force, instinct, vitality"),
    ("Kimi",     "Death",     "transformation, release, ancestors"),
    ("Manik'",   "Deer",      "healing hands, cooperation"),
    ("Lamat",    "Star",      "abundance, harmony, art"),
    ("Muluk",    "Water",     "emotion, offering, purification"),
    ("Ok",       "Dog",       "loyalty, guidance, the heart's law"),
    ("Chuwen",   "Monkey",    "play, craft, the weaver of time"),
    ("Eb'",      "Grass/Road",  "the human path, cooperation"),
    ("B'en",     "Reed",      "authority, home, the pillar"),
    ("Ix",       "Jaguar",    "earth magic, shamanic power"),
    ("Men",      "Eagle",     "vision, ambition, the wide view"),
    ("Kib'",     "Owl/Vulture", "wisdom, forgiveness, endings"),
    ("Kab'an",   "Earth",     "synchronicity, intelligence, the world"),
    ("Etz'nab'", "Flint",     "truth, clarity, the mirror"),
    ("Kawak",    "Storm",     "purification, catalysis, renewal"),
    ("Ajaw",     "Sun/Lord",  "enlightenment, completion, the flowering self"),
]
assert len(DAY_SIGNS) == 20

# 4 Ajaw is the anchor: Ajaw is the 20th sign (index 19).
_AJAW_INDEX = 19
_ANCHOR_TONE = 4


def get_julian_day_number(d: date) -> int:
    """Whole-day Julian Day Number for a Gregorian calendar date, via
    pyswisseph (already a dependency of this project) rather than
    hand-rolled proleptic-calendar arithmetic.

    Computed at NOON, not midnight: by convention JD X.0 falls at noon UT,
    so noon of a given calendar date is exactly the integer JDN for that
    date with no rounding needed. Midnight would give JDN-0.5, and
    round()-ing that off falls on the exact .5 boundary where Python's
    banker's rounding silently rounds to the wrong (even) integer half the
    time -- this cost a real day of drift the first time this was written,
    caught only because the anchor-date test below failed by exactly 1."""
    jd = swe.julday(d.year, d.month, d.day, 12.0)
    return int(round(jd))


# ---------------------------------------------------------------------------
# CORE LOOKUP -- verified against two independent reference dates (see
# module docstring and the test run in chat).
# ---------------------------------------------------------------------------
def date_to_tzolkin(d: date) -> dict:
    """Gregorian date -> Tzolkin reading: day sign, tone, trecena, kin
    number (1-260 position in the current round), and night lord."""
    jdn = get_julian_day_number(d)
    offset = jdn - GMT_CORRELATION_JDN

    tone = ((_ANCHOR_TONE - 1 + offset) % 13) + 1
    day_sign_index = (_AJAW_INDEX + offset) % 20
    day_sign_name, day_sign_glyph, day_sign_keyword = DAY_SIGNS[day_sign_index]

    # Trecena: the day sign that had tone=1 within this 13-day block --
    # i.e. step back (tone-1) days in day-sign-index space.
    trecena_index = (day_sign_index - (tone - 1)) % 20
    trecena_name, _tg, _tk = DAY_SIGNS[trecena_index]

    kin = (offset % 260) + 1
    night_lord = (offset % 9) + 1

    return {
        "gregorian_date": d.isoformat(),
        "day_sign": day_sign_name,
        "day_sign_glyph": day_sign_glyph,
        "day_sign_keyword": day_sign_keyword,
        "tone": tone,
        "trecena": trecena_name,
        "kin": kin,
        "night_lord": night_lord,
        "reading": f"{tone} {day_sign_name}",
    }


def tzolkin_occurrences_near(
    day_sign: str, tone: int, near_date: date, count: int = 3
) -> List[str]:
    """Nearest Gregorian dates (on/after near_date) matching a given
    (day_sign, tone) pair. The Tzolkin has no absolute epoch in ordinary
    use -- a given combination recurs every 260 days indefinitely -- so
    this is the closest honest analogue to calendar_bridge.py's reverse
    lookup, which resolves to one unique date because the Cosmic Calendar
    does have a "Cosmic Year" epoch and this doesn't."""
    day_sign = day_sign.strip().capitalize()
    matches = [name for name, *_ in DAY_SIGNS if name.lower() == day_sign.lower()]
    if not matches:
        return []
    target_index = [n for n, *_ in DAY_SIGNS].index(matches[0])

    jdn = get_julian_day_number(near_date)
    offset = jdn - GMT_CORRELATION_JDN
    current_tone = ((_ANCHOR_TONE - 1 + offset) % 13) + 1
    current_index = (_AJAW_INDEX + offset) % 20

    # Solve for the smallest non-negative delta where both cycles align:
    # delta ≡ (target_index - current_index) mod 20
    # delta ≡ (tone - current_tone) mod 13
    tone_delta = (tone - current_tone) % 13
    sign_delta = (target_index - current_index) % 20
    delta = None
    for k in range(13):
        candidate = tone_delta + 13 * k
        if candidate % 20 == sign_delta:
            delta = candidate
            break
    if delta is None:
        return []  # shouldn't happen: gcd(13,20)=1 guarantees a solution

    out = []
    d = near_date + timedelta(days=delta)
    for _ in range(count):
        out.append(d.isoformat())
        d += timedelta(days=260)
    return out


# ---------------------------------------------------------------------------
# TREE OF LIFE -- CONSTRUCTED interpretation. See module docstring.
# ---------------------------------------------------------------------------
TREE_OF_LIFE_PAST_TRECENAS = 1     # 1 trecena = 13 days back
TREE_OF_LIFE_FUTURE_TRECENAS = 1   # 13 days forward
TREE_OF_LIFE_MASCULINE_KIN = 4     # kept small and different from PAST/FUTURE's
TREE_OF_LIFE_FEMININE_KIN = 4      # 13-day offset so all four positions differ
# NOTE: deliberately NOT 10 (half of the 20-day sign cycle) -- +10 and -10
# both reduce to the same residue mod 20, which would make masculine and
# feminine always land on the identical day sign (differing only in tone)
# by mathematical necessity, not by design. Caught by inspecting actual
# output before shipping, not assumed safe from the formula alone.


def tree_of_life(d: date) -> dict:
    """5-position Tree of Life: center + past/future/masculine/feminine.
    CONSTRUCTED, not verified -- see module docstring before treating any
    position but 'center' as authoritative."""
    center = date_to_tzolkin(d)
    past = date_to_tzolkin(d - timedelta(days=13 * TREE_OF_LIFE_PAST_TRECENAS))
    future = date_to_tzolkin(d + timedelta(days=13 * TREE_OF_LIFE_FUTURE_TRECENAS))
    masculine = date_to_tzolkin(d - timedelta(days=TREE_OF_LIFE_MASCULINE_KIN))
    feminine = date_to_tzolkin(d + timedelta(days=TREE_OF_LIFE_FEMININE_KIN))

    return {
        "center_date": d.isoformat(),
        "center": center,
        "past": past,
        "future": future,
        "masculine": masculine,
        "feminine": feminine,
        "note": ("Past/future/masculine/feminine are a constructed, symmetric "
                 "interpretation -- the source material describes the concept "
                 "but not the formula. Not verified against any specific "
                 "site's actual method. The 'complete... nine' version from "
                 "the source is not implemented -- no textual basis for what "
                 "the other 4 positions would be."),
    }
