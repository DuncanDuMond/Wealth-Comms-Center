#!/usr/bin/env python3
"""
64-Gate Human Design Number System
═══════════════════════════════════════════════════════════════════════════════
Lays the Human-Design I Ching gate wheel over the sidereal ecliptic, wired to
wealth_algorithm.py's Lahiri / 13-sign (IAU / Ophiuchus) engine.  Each of the
64 gates is keyed to the chemical element whose atomic number equals the gate
number  (Gate N  <->  element Z = N,  Hydrogen..Gadolinium).

Anchor            : Gate 41 begins at 2°23'23" ("Aquarius") = 296.843500°
                    sidereal ecliptic longitude, exactly as supplied.
Gate width        : 360° / 64 = 5.625°  (fixed, non-negotiable arithmetic)
Line width (bonus): 5.625° / 6 = 0.9375° — Human Design's line-level
                    subdivision, included as a free extra field on every
                    lookup; the requested deliverable is gate-resolution.
Wheel direction   : gates advance with increasing sidereal longitude, in the
                    canonical Human Design mandala order (41→19→13→49→...).

Data correction   : the source list contained "34 – Xenon" a second time
                    (Gate 34 is already Selenium, Se, Z=34). Xenon's atomic
                    number is 54, and Gate 54 was the only gate 1-64 missing
                    from the list — so this module uses:
                        54 – Xenon (Xe, Z=54) – 歸妹 (guī mèi)
                    Gate 41's own hexagram wasn't given (only its starting
                    degree was) — filled in as 損 (sǔn), I Ching 41, "Decrease".
                    A self-check at import time (_validate) re-proves both:
                    every gate's element Z matches its gate number, all 64
                    hexagrams are distinct, and the 64 gates tile 360° exactly.

Reference frame   : this "Aquarius" anchor is treated as a self-contained
                    sidereal reference point, kept independent of the
                    _13SIGN_TROP / sign_sidereal_13() IAU-constellation table
                    already in wealth_algorithm.py — the two do not share a
                    boundary edge (wealth_algorithm.py's own table currently
                    resolves sidereal Aquarius to ≈303.03°, ~8.6° from the
                    ≈294.45° implied here). They're independent overlays on
                    the same 360° sidereal ring, like two hands on one clock
                    face — see bodies_to_gates() / print_chart_gates() for
                    where the two rings are read out side by side.

House cross-ref   : chart mode also reports each body's House (1-12), via
                    wealth_algorithm.house_of_sign() — a third, independent
                    overlay on the same sidereal ring: fixed sign-based
                    houses, not Ascendant-derived, wheel starting at
                    Sagittarius. See wealth_algorithm.py's HOUSES table for
                    the full house/constellation/ruler definitions.

Usage             : python human_design_gates.py                       (static 64-gate wheel)
                    python human_design_gates.py --sid-lon 118.2         (single longitude lookup)
                    python human_design_gates.py --date 1990-06-15 --time 14:30:00
                        --lat 40.71 --lon -74.01 --name Alice            (full 14-body chart)
                        [--output alice_gates.json]
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# wealth_algorithm.py + pyswisseph are only required for chart mode; the
# gate-wheel math itself is pure arithmetic and works without either.
# Note: wealth_algorithm.py calls sys.exit() at import time if pyswisseph
# is missing — that's a SystemExit, not an ImportError, so swisseph's own
# availability is checked FIRST and wealth_algorithm is only imported when
# it's present. (SystemExit is also caught defensively below, in case a
# future edit to wealth_algorithm.py adds another top-level exit.)
try:
    import swisseph as swe
    _HAS_SWISSEPH = True
except ImportError:
    swe = None
    _HAS_SWISSEPH = False

wa = None
_HAS_EPHEMERIS = False
if _HAS_SWISSEPH:
    try:
        import wealth_algorithm as wa
        _HAS_EPHEMERIS = True
    except (ImportError, SystemExit):
        wa = None
        _HAS_EPHEMERIS = False

# ════════════════════════════════════════════════════════════════════════════
#  WHEEL GEOMETRY
# ════════════════════════════════════════════════════════════════════════════
GATE_41_DMS:   tuple = (2, 23, 23)          # 2°23'23" — as supplied
GATE_41_START: float = 296.843500           # sidereal ecliptic longitude
GATE_WIDTH:    float = 360.0 / 64           # 5.625° exactly
LINE_WIDTH:    float = GATE_WIDTH / 6       # 0.9375° — bonus line resolution

# Wheel order (Human Design mandala sequence), starting at Gate 41.
# Position 0 sits at GATE_41_START; each later position advances +5.625°.
GATE_WHEEL_SEQUENCE: List[int] = [
    41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42,
     3, 27, 24,  2, 23,  8, 20, 16, 35, 45, 12, 15, 52, 39, 53,
    62, 56, 31, 33,  7,  4, 29, 59, 40, 64, 47,  6, 46, 18, 48,
    57, 32, 50, 28, 44,  1, 43, 14, 34,  9,  5, 26, 11, 10, 58,
    38, 54, 61, 60,
]

# ════════════════════════════════════════════════════════════════════════════
#  GATE CATALOG    Gate N  <->  element Z = N  <->  I Ching hexagram N
# ════════════════════════════════════════════════════════════════════════════
GATE_ELEMENTS: Dict[int, dict] = {
    1:  {"z": 1,  "element": "Hydrogen",     "symbol": "H",  "hanzi": "乾",   "pinyin": "qián"},
    2:  {"z": 2,  "element": "Helium",       "symbol": "He", "hanzi": "坤",   "pinyin": "kūn"},
    3:  {"z": 3,  "element": "Lithium",      "symbol": "Li", "hanzi": "屯",   "pinyin": "zhūn"},
    4:  {"z": 4,  "element": "Beryllium",    "symbol": "Be", "hanzi": "蒙",   "pinyin": "méng"},
    5:  {"z": 5,  "element": "Boron",        "symbol": "B",  "hanzi": "需",   "pinyin": "xū"},
    6:  {"z": 6,  "element": "Carbon",       "symbol": "C",  "hanzi": "訟",   "pinyin": "sòng"},
    7:  {"z": 7,  "element": "Nitrogen",     "symbol": "N",  "hanzi": "師",   "pinyin": "shī"},
    8:  {"z": 8,  "element": "Oxygen",       "symbol": "O",  "hanzi": "比",   "pinyin": "bǐ"},
    9:  {"z": 9,  "element": "Fluorine",     "symbol": "F",  "hanzi": "小畜", "pinyin": "xiǎo xù"},
    10: {"z": 10, "element": "Neon",         "symbol": "Ne", "hanzi": "履",   "pinyin": "lǚ"},
    11: {"z": 11, "element": "Sodium",       "symbol": "Na", "hanzi": "泰",   "pinyin": "tài"},
    12: {"z": 12, "element": "Magnesium",    "symbol": "Mg", "hanzi": "否",   "pinyin": "pǐ"},
    13: {"z": 13, "element": "Aluminium",    "symbol": "Al", "hanzi": "同人", "pinyin": "tóng rén"},
    14: {"z": 14, "element": "Silicon",      "symbol": "Si", "hanzi": "大有", "pinyin": "dà yǒu"},
    15: {"z": 15, "element": "Phosphorus",   "symbol": "P",  "hanzi": "謙",   "pinyin": "qiān"},
    16: {"z": 16, "element": "Sulfur",       "symbol": "S",  "hanzi": "豫",   "pinyin": "yù"},
    17: {"z": 17, "element": "Chlorine",     "symbol": "Cl", "hanzi": "隨",   "pinyin": "suí"},
    18: {"z": 18, "element": "Argon",        "symbol": "Ar", "hanzi": "蠱",   "pinyin": "gǔ"},
    19: {"z": 19, "element": "Potassium",    "symbol": "K",  "hanzi": "臨",   "pinyin": "lín"},
    20: {"z": 20, "element": "Calcium",      "symbol": "Ca", "hanzi": "觀",   "pinyin": "guān"},
    21: {"z": 21, "element": "Scandium",     "symbol": "Sc", "hanzi": "噬嗑", "pinyin": "shì kè"},
    22: {"z": 22, "element": "Titanium",     "symbol": "Ti", "hanzi": "賁",   "pinyin": "bì"},
    23: {"z": 23, "element": "Vanadium",     "symbol": "V",  "hanzi": "剝",   "pinyin": "bō"},
    24: {"z": 24, "element": "Chromium",     "symbol": "Cr", "hanzi": "復",   "pinyin": "fù"},
    25: {"z": 25, "element": "Manganese",    "symbol": "Mn", "hanzi": "无妄", "pinyin": "wú wàng"},
    26: {"z": 26, "element": "Iron",         "symbol": "Fe", "hanzi": "大畜", "pinyin": "dà xù"},
    27: {"z": 27, "element": "Cobalt",       "symbol": "Co", "hanzi": "頤",   "pinyin": "yí"},
    28: {"z": 28, "element": "Nickel",       "symbol": "Ni", "hanzi": "大過", "pinyin": "dà guò"},
    29: {"z": 29, "element": "Copper",       "symbol": "Cu", "hanzi": "坎",   "pinyin": "kǎn"},
    30: {"z": 30, "element": "Zinc",         "symbol": "Zn", "hanzi": "離",   "pinyin": "lí"},
    31: {"z": 31, "element": "Gallium",      "symbol": "Ga", "hanzi": "咸",   "pinyin": "xián"},
    32: {"z": 32, "element": "Germanium",    "symbol": "Ge", "hanzi": "恆",   "pinyin": "héng"},
    33: {"z": 33, "element": "Arsenic",      "symbol": "As", "hanzi": "遯",   "pinyin": "dùn"},
    34: {"z": 34, "element": "Selenium",     "symbol": "Se", "hanzi": "大壯", "pinyin": "dà zhuàng"},
    35: {"z": 35, "element": "Bromine",      "symbol": "Br", "hanzi": "晉",   "pinyin": "jìn"},
    36: {"z": 36, "element": "Krypton",      "symbol": "Kr", "hanzi": "明夷", "pinyin": "míng yí"},
    37: {"z": 37, "element": "Rubidium",     "symbol": "Rb", "hanzi": "家人", "pinyin": "jiā rén"},
    38: {"z": 38, "element": "Strontium",    "symbol": "Sr", "hanzi": "睽",   "pinyin": "kuí"},
    39: {"z": 39, "element": "Yttrium",      "symbol": "Y",  "hanzi": "蹇",   "pinyin": "jiǎn"},
    40: {"z": 40, "element": "Zirconium",    "symbol": "Zr", "hanzi": "解",   "pinyin": "jiě"},
    41: {"z": 41, "element": "Niobium",      "symbol": "Nb", "hanzi": "損",   "pinyin": "sǔn"},
    42: {"z": 42, "element": "Molybdenum",   "symbol": "Mo", "hanzi": "益",   "pinyin": "yì"},
    43: {"z": 43, "element": "Technetium",   "symbol": "Tc", "hanzi": "夬",   "pinyin": "guài"},
    44: {"z": 44, "element": "Ruthenium",    "symbol": "Ru", "hanzi": "姤",   "pinyin": "gòu"},
    45: {"z": 45, "element": "Rhodium",      "symbol": "Rh", "hanzi": "萃",   "pinyin": "cuì"},
    46: {"z": 46, "element": "Palladium",    "symbol": "Pd", "hanzi": "升",   "pinyin": "shēng"},
    47: {"z": 47, "element": "Silver",       "symbol": "Ag", "hanzi": "困",   "pinyin": "kùn"},
    48: {"z": 48, "element": "Cadmium",      "symbol": "Cd", "hanzi": "井",   "pinyin": "jǐng"},
    49: {"z": 49, "element": "Indium",       "symbol": "In", "hanzi": "革",   "pinyin": "gé"},
    50: {"z": 50, "element": "Tin",          "symbol": "Sn", "hanzi": "鼎",   "pinyin": "dǐng"},
    51: {"z": 51, "element": "Antimony",     "symbol": "Sb", "hanzi": "震",   "pinyin": "zhèn"},
    52: {"z": 52, "element": "Tellurium",    "symbol": "Te", "hanzi": "艮",   "pinyin": "gèn"},
    53: {"z": 53, "element": "Iodine",       "symbol": "I",  "hanzi": "漸",   "pinyin": "jiàn"},
    54: {"z": 54, "element": "Xenon",        "symbol": "Xe", "hanzi": "歸妹", "pinyin": "guī mèi"},
    55: {"z": 55, "element": "Caesium",      "symbol": "Cs", "hanzi": "豐",   "pinyin": "fēng"},
    56: {"z": 56, "element": "Barium",       "symbol": "Ba", "hanzi": "旅",   "pinyin": "lǚ"},
    57: {"z": 57, "element": "Lanthanum",    "symbol": "La", "hanzi": "巽",   "pinyin": "xùn"},
    58: {"z": 58, "element": "Cerium",       "symbol": "Ce", "hanzi": "兌",   "pinyin": "duì"},
    59: {"z": 59, "element": "Praseodymium", "symbol": "Pr", "hanzi": "渙",   "pinyin": "huàn"},
    60: {"z": 60, "element": "Neodymium",    "symbol": "Nd", "hanzi": "節",   "pinyin": "jié"},
    61: {"z": 61, "element": "Promethium",   "symbol": "Pm", "hanzi": "中孚", "pinyin": "zhōng fú"},
    62: {"z": 62, "element": "Samarium",     "symbol": "Sm", "hanzi": "小過", "pinyin": "xiǎo guò"},
    63: {"z": 63, "element": "Europium",     "symbol": "Eu", "hanzi": "既濟", "pinyin": "jì jì"},
    64: {"z": 64, "element": "Gadolinium",   "symbol": "Gd", "hanzi": "未濟", "pinyin": "wèi jì"},
}

# Z=1..64 in order, used only by _validate() to re-prove the Gate == Z claim.
_ATOMIC_NUMBER_ORDER: List[str] = [
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd",
]

# Absolute sidereal start degree for every gate, derived from the anchor.
GATE_START_DEG: Dict[int, float] = {
    gate: (GATE_41_START + i * GATE_WIDTH) % 360.0
    for i, gate in enumerate(GATE_WHEEL_SEQUENCE)
}


def _validate() -> None:
    """Self-check run at import time — see 'Data correction' note above."""
    assert len(GATE_WHEEL_SEQUENCE) == 64, "wheel must list exactly 64 gates"
    assert sorted(GATE_WHEEL_SEQUENCE) == list(range(1, 65)), \
        "wheel sequence must be a permutation of 1-64 (no gaps, no repeats)"
    assert set(GATE_ELEMENTS) == set(range(1, 65)), \
        "GATE_ELEMENTS must define all 64 gates"
    for gate, data in GATE_ELEMENTS.items():
        z = _ATOMIC_NUMBER_ORDER.index(data["symbol"]) + 1
        assert z == gate == data["z"], (
            f"Gate {gate}: element {data['symbol']} has Z={z}, "
            f"expected Z={gate}"
        )
    hexagrams = [d["hanzi"] for d in GATE_ELEMENTS.values()]
    assert len(set(hexagrams)) == 64, "all 64 hexagrams must be distinct"
    assert abs(GATE_WIDTH * 64 - 360.0) < 1e-9, "64 gates must tile 360° exactly"


_validate()


# ════════════════════════════════════════════════════════════════════════════
#  FORMATTING
# ════════════════════════════════════════════════════════════════════════════
def dms_string(deg: float) -> str:
    """Decimal degrees -> D°MM'SS" string (mirrors wealth_algorithm._dms)."""
    deg = deg % 360.0
    d = int(deg)
    rem = (deg - d) * 60
    m = int(rem)
    s = round((rem - m) * 60)
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d}\u00b0{m:02d}'{s:02d}\""


# ════════════════════════════════════════════════════════════════════════════
#  LOOKUP ENGINE
# ════════════════════════════════════════════════════════════════════════════
def _wrap_deg(x: float, ndigits: int = 8) -> float:
    """
    Wrap to [0, 360) after rounding away sub-microdegree float noise.
    Without this, a value that is mathematically exactly on a gate boundary
    (e.g. the anchor plus an exact multiple of 360°) can land a few
    femtodegrees on the wrong side of zero, and `%` sends that sliver
    wrapping almost all the way around to 359.999... instead of 0 — which
    then floors into the *previous* gate instead of the current one.
    8 decimal places (~1 mm at Earth's surface) is far finer than any
    ephemeris or DMS-second input, so nothing meaningful is lost.
    """
    return round(x, ndigits) % 360.0


def gate_slot_index(sid_lon: float) -> int:
    """0-63 wheel-slot index, measured forward from the Gate 41 anchor."""
    offset = _wrap_deg(sid_lon - GATE_41_START)
    return min(int(offset // GATE_WIDTH), 63)


def gate_for_longitude(sid_lon: float) -> dict:
    """
    Resolve a sidereal ecliptic longitude to its Gate (+ bonus Line 1-6).
    `sid_lon` must already be sidereal (Lahiri) — this module never applies
    an ayanamsa correction itself; chart mode gets sidereal longitudes
    straight from wealth_algorithm.calc_planets(..., sidereal=True).
    """
    sid_lon = _wrap_deg(sid_lon)
    slot = gate_slot_index(sid_lon)
    gate = GATE_WHEEL_SEQUENCE[slot]
    start = GATE_START_DEG[gate]
    deg_in_gate = _wrap_deg(sid_lon - start)
    line = min(int(deg_in_gate // LINE_WIDTH) + 1, 6)
    data = GATE_ELEMENTS[gate]
    return {
        "gate":            gate,
        "line":            line,
        "element":         data["element"],
        "symbol":          data["symbol"],
        "z":               data["z"],
        "hexagram_hanzi":  data["hanzi"],
        "hexagram_pinyin": data["pinyin"],
        "sid_lon":         round(sid_lon, 4),
        "sid_lon_dms":     dms_string(sid_lon),
        "start_deg":       round(start, 4),
        "deg_in_gate":     round(deg_in_gate, 4),
    }


def bodies_to_gates(sid_lons: Dict[str, float]) -> Dict[str, dict]:
    """{body: sidereal_longitude} -> {body: gate_info}. Feed it the `lons`
    dict returned by wealth_algorithm.calc_planets()/all_body_positions()."""
    return {name: gate_for_longitude(lon) for name, lon in sid_lons.items()}


def wheel_table() -> List[dict]:
    """Full 64-row wheel, in wheel order starting at Gate 41."""
    rows = []
    for i, gate in enumerate(GATE_WHEEL_SEQUENCE):
        start = GATE_START_DEG[gate]
        end = (start + GATE_WIDTH) % 360.0
        data = GATE_ELEMENTS[gate]
        rows.append({
            "slot":       i,
            "gate":       gate,
            "z":          data["z"],
            "symbol":     data["symbol"],
            "element":    data["element"],
            "hexagram":   f"{data['hanzi']} ({data['pinyin']})",
            "start_deg":  round(start, 4),
            "start_dms":  dms_string(start),
            "end_dms":    dms_string(end),
        })
    return rows


# ════════════════════════════════════════════════════════════════════════════
#  REPORTS
# ════════════════════════════════════════════════════════════════════════════
def print_wheel_table() -> None:
    rows = wheel_table()
    W = 88
    print(f"\n{'═' * W}")
    print("  64-GATE HUMAN DESIGN WHEEL  ·  Sidereal Ecliptic  ·  Gate = Element Z")
    print(f"{'═' * W}")
    print(f"  Anchor : Gate 41 @ {GATE_41_DMS[0]}\u00b0{GATE_41_DMS[1]:02d}'{GATE_41_DMS[2]:02d}\""
          f"  =  {GATE_41_START:.4f}\u00b0 sidereal   ·   width {GATE_WIDTH}\u00b0/gate")
    print(f"  {'─' * W}")
    print(f"  {'#':>2} {'GATE':>4}  {'EL':<3}{'Z':>3}  {'HEXAGRAM':<20}{'START':>13}{'END':>13}")
    print(f"  {'─' * W}")
    for r in rows:
        print(f"  {r['slot']:>2} {r['gate']:>4}  {r['symbol']:<3}{r['z']:>3}  "
              f"{r['hexagram']:<20}{r['start_dms']:>13}{r['end_dms']:>13}")
    print(f"{'═' * W}\n")


def print_chart_gates(
    name: str, dt: datetime,
    body_info: Dict[str, dict], gate_info: Dict[str, dict],
) -> None:
    W = 92
    print(f"\n{'═' * W}")
    print(f"  64-GATE PLACEMENTS  ·  {name}")
    print(f"{'═' * W}")
    print(f"  Date/Time : {dt.strftime('%Y-%m-%d  %H:%M:%S')} UTC")
    print("  Mode      : Sidereal · Lahiri · 13-Sign (IAU/Ophiuchus) + 64-Gate overlay + Houses")
    print(f"  {'─' * W}")
    print(f"\n  {'BODY':<20}{'CONSTELLATION':<15}{'HOUSE':<7}{'GATE.LINE':<11}{'ELEMENT':<16}HEXAGRAM")
    print(f"  {'─' * W}")
    for body, g in gate_info.items():
        constellation = body_info.get(body, {}).get("sign", "\u2014")
        house = wa.house_of_sign(constellation) if wa else None
        house_str = f"{house}" if house is not None else "\u2014"
        gate_line = f"{g['gate']}.{g['line']}"
        elem_str = f"{g['element']} ({g['symbol']})"
        hexagram = f"{g['hexagram_hanzi']} ({g['hexagram_pinyin']})"
        print(f"  {body:<20}{constellation:<15}{house_str:<7}{gate_line:<11}{elem_str:<16}{hexagram}")
    print(f"{'═' * W}\n")


def export_chart_gates(
    outpath: str, name: str, dt: datetime,
    body_info: Dict[str, dict], gate_info: Dict[str, dict],
) -> None:
    payload = {
        "meta": {
            "name":         name,
            "datetime_utc": dt.isoformat(),
            "mode":         "sidereal_lahiri_13sign_64gate_houses",
        },
        "bodies": {
            body: {
                "lon":             body_info.get(body, {}).get("lon"),
                "constellation":   body_info.get(body, {}).get("sign"),
                "deg_in_sign":     body_info.get(body, {}).get("deg_in_sign"),
                "retro":           body_info.get(body, {}).get("retro"),
                "house":           wa.house_of_sign(body_info.get(body, {}).get("sign")) if wa else None,
                "gate":            g["gate"],
                "line":            g["line"],
                "element":         g["element"],
                "symbol":          g["symbol"],
                "z":               g["z"],
                "hexagram_hanzi":  g["hexagram_hanzi"],
                "hexagram_pinyin": g["hexagram_pinyin"],
            }
            for body, g in gate_info.items()
        },
    }
    out_path = Path(outpath)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  \u2713  JSON saved \u2192 {out_path}")


# ════════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════════
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="human_design_gates",
        description="64-Gate Human Design wheel on the sidereal ecliptic "
                     "(Gate N <-> element Z=N <-> I Ching hexagram N).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python human_design_gates.py\n"
            "      -> prints the static 64-gate wheel\n"
            "  python human_design_gates.py --sid-lon 118.2\n"
            "      -> single sidereal-longitude Gate lookup\n"
            "  python human_design_gates.py --date 1990-06-15 --time 14:30:00"
            " --lat 40.71 --lon -74.01 --name Alice\n"
            "      -> full 14-body chart (requires wealth_algorithm.py alongside this file)\n"
            "         add --output alice_gates.json to export\n"
        ),
    )
    p.add_argument("--sid-lon", type=float, default=None, dest="sid_lon",
                   help="Sidereal ecliptic longitude (0-360) for a single Gate lookup. "
                        "Takes priority over chart-mode arguments if both are given.")
    p.add_argument("--name", default=None, help="Name of native (chart mode)")
    p.add_argument("--date", default=None, help="Birth date YYYY-MM-DD (UTC, chart mode)")
    p.add_argument("--time", default=None, help="Birth time HH:MM:SS (UTC, chart mode)")
    p.add_argument("--lat", type=float, default=None, help="Latitude, N positive (chart mode)")
    p.add_argument("--lon", type=float, default=None, help="Geographic longitude, E positive (chart mode)")
    p.add_argument("--ephe-path", default=None, dest="ephe_path", help="Custom ephemeris directory")
    p.add_argument("--output", default=None, help="Export chart-mode report to a .json path")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    if args.sid_lon is not None:
        info = gate_for_longitude(args.sid_lon)
        print(f"\n  {info['sid_lon']:.4f}\u00b0 sidereal  ({info['sid_lon_dms']})  \u2192  "
              f"Gate {info['gate']}.{info['line']}  \u00b7  "
              f"{info['element']} ({info['symbol']}, Z={info['z']})  \u00b7  "
              f"{info['hexagram_hanzi']} ({info['hexagram_pinyin']})\n")
        return

    if args.date:
        if not _HAS_EPHEMERIS:
            sys.exit("[ERROR] wealth_algorithm.py (and pyswisseph) must be "
                      "importable alongside human_design_gates.py for chart mode.")
        if args.lat is None or args.lon is None:
            sys.exit("[ERROR] --lat and --lon are required for chart mode.")
        time_str = args.time or "12:00:00"
        try:
            dt = datetime.strptime(f"{args.date} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            sys.exit(f"[ERROR] Date/time parse error: {exc}")

        name = args.name or "Native"
        wa.setup_ephemeris(args.ephe_path)
        jd = wa.get_julian_day(dt)
        # Gates are anchored on the sidereal wheel, so chart mode always
        # pulls sidereal longitudes — there is no tropical Gate mode.
        lons, _weights, body_info = wa.all_body_positions(jd, args.lat, args.lon, sidereal=True)
        gate_info = bodies_to_gates(lons)

        print_chart_gates(name, dt, body_info, gate_info)
        if args.output:
            export_chart_gates(args.output, name, dt, body_info, gate_info)
        return

    # No arguments at all -> show the static wheel.
    print_wheel_table()


if __name__ == "__main__":
    main()
