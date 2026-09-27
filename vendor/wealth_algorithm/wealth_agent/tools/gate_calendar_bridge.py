#!/usr/bin/env python3
"""
gate_calendar_bridge.py
════════════════════════════════════════════════════════════════════════════
Now wired directly to the real calendar_bridge.py (uploaded and extended in
place -- see BOOST_DAY_GATE and the gate_info/day_gate params on
apply_cosmic_boosts() there). This file computes the three pieces that
extended function needs and hands them off:

    day_gate()             -- today's Sun-Gate + House (+ cosmic_calendar's card, for context)
    apply_all_cosmic_boosts() -- orchestrates cosmic_info + gate_info + day_gate
                                 into one call to calendar_bridge.apply_cosmic_boosts()

gate_boost_weights() (the standalone {body: multiplier} view) is kept
as-is for lighter use -- e.g. the wealth_agent tool, or anywhere you want
just the day-gate effect without running a full score_dict through the
scoring pipeline first.

Concept — "Day Gate": the Gate the Sun sidereally occupies on a civil date.
This isn't an invented mechanic — it's the same machinery Human Design
already uses to find a person's own Sun gate, just pointed at a calendar
date instead of a birth date. A body in the chart whose own Gate matches
the day's Sun-Gate earns the boost, on the same logic as a planet echoing
its month's ruler: alignment between "what the day itself is" and "where a
body sits" is what triggers each of these three tiers.

Boost size: BOOST_DAY_GATE = 1.15 (set in calendar_bridge.py, next to the
other two), matching the month-ruler tier's size — landing on the Sun's one
current Gate out of 64 is a tighter target than either existing category.

cosmic_calendar.py's card/suit is surfaced in print_day_gate() purely for
context — the day-gate boost itself is driven by the Sun's real sidereal
position, not the card table; the card/suit tier is the existing
SUIT_PLANET_GROUPS mechanism in calendar_bridge.py, untouched here.

House: day_gate() also reports the Sun's House (1-12) via
wealth_algorithm.house_for_longitude() — display/context only, same as the
card. There's no fourth "house" boost tier here; that would be a new
scoring mechanic, not something this update asked for. Straightforward to
add later the same way the day-gate tier was, if wanted.

Usage       : python gate_calendar_bridge.py                (today's Day Gate)
              python gate_calendar_bridge.py 2026-12-25      (a specific date)
════════════════════════════════════════════════════════════════════════════
"""

import sys
from datetime import date, datetime
from typing import Dict, Optional

import swisseph as swe
from . import calendar_bridge as cb
from . import human_design_gates as hdg
from . import chart as wa


def day_gate(greg_date: date, hour: int = 12, ephe_path: Optional[str] = None) -> dict:
    """
    The Gate (+ Line) and House the Sun sidereally occupies on a civil date,
    with that date's cosmic_calendar card attached for context.  `hour`
    sets the UTC hour used for the Sun position (default noon — the Sun
    moves <1° across a day, far less than a 5.625° gate width, so this
    choice barely matters except right at a gate-boundary crossing).
    """
    if ephe_path:
        wa.setup_ephemeris(ephe_path)
    else:
        wa._ensure_ephemeris()
    dt = datetime(greg_date.year, greg_date.month, greg_date.day, hour, 0, 0)
    jd = wa.get_julian_day(dt.year, dt.month, dt.day, float(hour))
    lons, _retro, _errors = wa.calc_planets(jd, sidereal=True)
    sun_gate = hdg.gate_for_longitude(lons["Sun"])
    house = wa.house_for_longitude(lons["Sun"], swe.get_ayanamsa_ut(jd))

    cosmic_info = cb.date_to_cosmic_raw(greg_date)
    card = cosmic_info["card"] if cosmic_info else None

    return {
        "date":            greg_date.isoformat(),
        "sun_sid_lon":     sun_gate["sid_lon"],
        "house":           house,
        "gate":            sun_gate["gate"],
        "line":            sun_gate["line"],
        "element":         sun_gate["element"],
        "symbol":          sun_gate["symbol"],
        "hexagram_hanzi":  sun_gate["hexagram_hanzi"],
        "hexagram_pinyin": sun_gate["hexagram_pinyin"],
        "card":            card,   # (suit_symbol, value) or None (Leap Day edge case)
    }


def gate_boost_weights(
    chart_gate_info: Dict[str, dict],
    greg_date: date,
    boost: float = 1.15,
    hour: int = 12,
    ephe_path: Optional[str] = None,
) -> Dict[str, float]:
    """
    {body: multiplier} — `boost` where a body's own Gate matches the day's
    Sun-Gate, else 1.0 (no effect). `chart_gate_info` is exactly what
    human_design_gates.bodies_to_gates() returns. Lighter-weight than
    apply_all_cosmic_boosts() below: no score_dict / bodies_involved
    filtering, just the raw gate match per body.
    """
    today_gate = day_gate(greg_date, hour=hour, ephe_path=ephe_path)["gate"]
    return {
        body: (boost if g["gate"] == today_gate else 1.0)
        for body, g in chart_gate_info.items()
    }


def apply_all_cosmic_boosts(
    score_dict: dict,
    lons: Dict[str, float],
    greg_date: date,
    hour: int = 12,
    ephe_path: Optional[str] = None,
) -> dict:
    """
    One-call version of calendar_bridge.apply_cosmic_boosts() that also
    supplies the day-gate tier: computes cosmic_info, this chart's
    gate_info (from `lons`, e.g. from wealth_algorithm.all_body_positions),
    and today's Sun-Gate, then applies all three boost tiers -- month
    ruler, suit element, and day gate -- in one pass.
    """
    cosmic_info = cb.date_to_cosmic_raw(greg_date)
    if cosmic_info is None:
        raise ValueError(f"No cosmic position for {greg_date}")

    gate_info = hdg.bodies_to_gates(lons)
    today_gate = day_gate(greg_date, hour=hour, ephe_path=ephe_path)["gate"]

    return cb.apply_cosmic_boosts(
        score_dict, cosmic_info, gate_info=gate_info, day_gate=today_gate
    )


def print_day_gate(greg_date: date, hour: int = 12) -> None:
    d = day_gate(greg_date, hour=hour)
    card_str = f"{d['card'][1]}{d['card'][0]}" if d["card"] else "\u2014"
    print(f"\n  {d['date']}   Card: {card_str}   \u2192   "
          f"House {d['house']}  \u00b7  Day Gate {d['gate']}.{d['line']}  \u00b7  "
          f"{d['element']} ({d['symbol']})  \u00b7  "
          f"{d['hexagram_hanzi']} ({d['hexagram_pinyin']})\n")


if __name__ == "__main__":
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print_day_gate(target)
