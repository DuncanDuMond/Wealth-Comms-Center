"""
wealth_agent/tools/gates.py
════════════════════════════════════════════════════════════════════════════
Exposes human_design_gates.py + gate_calendar_bridge.py to wealth_agent's
tool-calling loop as three Anthropic-format tools:

    get_gate_for_longitude   atomic lookup — one sidereal longitude -> one Gate
    get_chart_gates          full chart    — birth data -> all 14 bodies' Gates + Houses
    get_day_gate             today's (or any date's) Sun-Gate + House + calendar card

I don't have agent_loop.py / tools/chart.py / cache.py in hand, so two
things here are my best-guess scaffolding rather than confirmed fact —
flagged inline with ASSUMPTION so they're easy to find and fix:

  1. Registration/dispatch shape. TOOLS is a plain list of schema dicts and
     HANDLERS maps name -> function(tool_input_dict) -> JSON-serializable
     dict, which is the shape most Anthropic-tool-loop implementations use.
     If agent_loop.py instead uses a class-based registry or a decorator,
     the schemas and handler bodies below don't need to change — only how
     they're plugged in at the bottom.

  2. Chart computation is self-contained (calls wa.all_body_positions
     directly) rather than accepting longitudes that tools/chart.py already
     computed this turn. Safer given I haven't seen chart.py's return
     shape, but it does mean get_chart_gates re-runs the ephemeris call
     independently. If cache.py memoizes chart-by-(date,time,lat,lon), route
     the call below through it instead of calling wa.all_body_positions
     directly, so a turn that calls both the chart tool and this one
     doesn't compute the same chart twice.
════════════════════════════════════════════════════════════════════════════
"""

from datetime import date as date_cls, datetime
from typing import Any, Dict

import gate_calendar_bridge as gcb
import human_design_gates as hdg
import wealth_algorithm as wa

# ════════════════════════════════════════════════════════════════════════════
#  TOOL SCHEMAS (Anthropic tool-use format)
# ════════════════════════════════════════════════════════════════════════════
GET_GATE_FOR_LONGITUDE_SCHEMA: Dict[str, Any] = {
    "name": "get_gate_for_longitude",
    "description": (
        "Resolve a single sidereal (Lahiri) ecliptic longitude to its Human "
        "Design Gate and Line (1-6), plus the Gate's keyed chemical element "
        "and I Ching hexagram. Use for a quick one-off lookup when a "
        "longitude is already known — no chart computation involved."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sidereal_longitude": {
                "type": "number",
                "description": "Sidereal ecliptic longitude in decimal degrees, 0-360.",
            }
        },
        "required": ["sidereal_longitude"],
    },
}

GET_CHART_GATES_SCHEMA: Dict[str, Any] = {
    "name": "get_chart_gates",
    "description": (
        "Compute the full 64-Gate placement (Gate, Line, element, hexagram, "
        "13-sign sidereal constellation, and House 1-12) for all 14 tracked "
        "bodies — 10 classical planets, True Black Moon Lilith, Lot of "
        "Fortune, Lot of Spirit, and White Moon Selena — in a birth or "
        "transit chart."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "date":      {"type": "string", "description": "Date, YYYY-MM-DD (UTC)."},
            "time":      {"type": "string", "description": "Time, HH:MM:SS (UTC). Defaults to 12:00:00 if omitted."},
            "latitude":  {"type": "number", "description": "Latitude, decimal degrees, north positive."},
            "longitude": {"type": "number", "description": "Geographic longitude, decimal degrees, east positive."},
            "name":      {"type": "string", "description": "Optional label for the native/chart."},
        },
        "required": ["date", "latitude", "longitude"],
    },
}

GET_DAY_GATE_SCHEMA: Dict[str, Any] = {
    "name": "get_day_gate",
    "description": (
        "Get the 'Day Gate' for a civil date -- the Gate and House the Sun "
        "sidereally occupies that day, plus the cosmic_calendar playing "
        "card for context. The Gate value is the same one calendar_bridge.py's "
        "day-gate boost tier uses: a body in a chart whose own Gate matches "
        "the Day Gate is 'in tune' with that day, the same way a planet "
        "ruling the cosmic month or the day's card-suit is."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date, YYYY-MM-DD. Defaults to today (UTC) if omitted.",
            }
        },
        "required": [],
    },
}

TOOLS = [GET_GATE_FOR_LONGITUDE_SCHEMA, GET_CHART_GATES_SCHEMA, GET_DAY_GATE_SCHEMA]


# ════════════════════════════════════════════════════════════════════════════
#  HANDLERS  —  each takes the parsed tool_input dict, returns JSON-serializable dict
# ════════════════════════════════════════════════════════════════════════════
def handle_get_gate_for_longitude(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    return hdg.gate_for_longitude(tool_input["sidereal_longitude"])


def handle_get_chart_gates(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    date = tool_input["date"]
    time_str = tool_input.get("time", "12:00:00")
    try:
        dt = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        return {"error": f"Date/time parse error: {exc}"}

    # ASSUMPTION 2 (see module docstring): route through cache.py here if
    # you have a per-turn chart cache, instead of calling this directly.
    wa.setup_ephemeris()
    jd = wa.get_julian_day(dt)
    lons, _weights, body_info = wa.all_body_positions(
        jd, tool_input["latitude"], tool_input["longitude"], sidereal=True
    )
    gate_info = hdg.bodies_to_gates(lons)

    bodies = {}
    for body, g in gate_info.items():
        bi = body_info.get(body, {})
        bodies[body] = {
            "constellation":   bi.get("sign"),
            "deg_in_sign":     bi.get("deg_in_sign"),
            "retro":           bi.get("retro"),
            "house":           wa.house_of_sign(bi.get("sign")),
            "gate":            g["gate"],
            "line":            g["line"],
            "element":         g["element"],
            "symbol":          g["symbol"],
            "z":               g["z"],
            "hexagram_hanzi":  g["hexagram_hanzi"],
            "hexagram_pinyin": g["hexagram_pinyin"],
        }

    return {
        "name":         tool_input.get("name", "Native"),
        "datetime_utc": dt.isoformat(),
        "mode":         "sidereal_lahiri_13sign_64gate_houses",
        "bodies":       bodies,
    }


def handle_get_day_gate(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    date_str = tool_input.get("date")
    try:
        d = date_cls.fromisoformat(date_str) if date_str else date_cls.today()
    except ValueError as exc:
        return {"error": f"Date parse error: {exc}"}

    d_gate = gcb.day_gate(d)
    return {
        "date":            d_gate["date"],
        "house":           d_gate["house"],
        "gate":            d_gate["gate"],
        "line":            d_gate["line"],
        "element":         d_gate["element"],
        "symbol":          d_gate["symbol"],
        "hexagram_hanzi":  d_gate["hexagram_hanzi"],
        "hexagram_pinyin": d_gate["hexagram_pinyin"],
        "card":            d_gate["card"],
    }


# ASSUMPTION 1 (see module docstring): adjust registration to match
# agent_loop.py's real dispatch convention; the functions above are the
# part that shouldn't need to change.
HANDLERS = {
    "get_gate_for_longitude": handle_get_gate_for_longitude,
    "get_chart_gates":        handle_get_chart_gates,
    "get_day_gate":           handle_get_day_gate,
}
