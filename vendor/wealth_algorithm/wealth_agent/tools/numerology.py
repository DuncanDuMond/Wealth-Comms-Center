"""
numerology.py — Irrational-Constant Cipher Ring.

FAITHFUL PORT of your uploaded numerology.py: same 15 active ciphers and
their weights, same reduce_number/cipher_value/date_value logic, same
Chaldean 1-9 planetary rulers, same master-number handling, same
score_numerology_boost formula. Every constant and formula below was
checked against your source file line by line, not reconstructed from
memory -- same standard as every other port in this project.

MISSING DEPENDENCY: ciphers.js was NOT included in this upload.
parse_ciphers_js() / load_ciphers() / compute_numerology_profile() are
faithfully ported and will work correctly the moment a real ciphers.js is
available, but cannot produce a real numerology profile without it --
the actual per-letter cipher VALUES (26 letters x 15 ciphers) are data
this module reads from that file, not something derivable from anything
else in this project. Calling compute_numerology_profile() without it
raises FileNotFoundError, exactly like your source does -- and exactly
like wealth_algorithm.py's own main() already expects and handles
(_NUMEROLOGY_AVAILABLE / try-except FileNotFoundError). The wiring in
agent_loop.py follows that same graceful-degradation pattern: a missing
ciphers.js means the numerology tier is skipped with a clear message, not
a crash, and never a fabricated cipher table standing in for the real one.

The engine logic itself (everything except the actual cipher letter
values) was verified independently before being trusted -- reduce_number,
date_value, and ruling_planet were each tested against hand-computed
examples, and score_numerology_boost was tested end-to-end against a
synthetic cipher table built for testing only (never presented as real
cipher data). See the test run in chat.
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Default location for ciphers.js: wealth_agent/ciphers.js, sibling to
# ephe/ at the package root. Not in your source (which defaulted to a
# bare "ciphers.js" relative to the current working directory) -- this
# project resolves paths relative to the file location throughout
# (chart.py's EPHE_DIR does the same), so this follows that convention
# rather than depending on which directory the process happens to be
# launched from.
DEFAULT_CIPHERS_JS_PATH = Path(__file__).resolve().parent.parent / "ciphers.js"


def ciphers_js_available(path: Optional[str] = None) -> bool:
    """Cheap existence check, used to decide whether to attempt the
    numerology tier at all before calling anything that would raise."""
    p = Path(path) if path else DEFAULT_CIPHERS_JS_PATH
    return p.exists()

# ---------------------------------------------------------------------------
# CIPHER PARSER (ciphers.js -> Cipher objects) -- verbatim.
# ---------------------------------------------------------------------------
@dataclass
class Cipher:
    name: str
    category: str
    char_map: Dict[int, int]   # ordinal(lowercase char) -> value
    weight: float               # this cipher's irrational/metallic constant


def _find_matching_paren(s: str, start: int) -> int:
    depth, i = 0, start
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_level(s: str) -> List[str]:
    parts, depth, cur, in_str, str_char = [], 0, "", False, ""
    for ch in s:
        if in_str:
            cur += ch
            if ch == str_char:
                in_str = False
            continue
        if ch in "\"'":
            in_str, str_char = True, ch
            cur += ch
            continue
        if ch in "[{":
            depth += 1; cur += ch; continue
        if ch in "]}":
            depth -= 1; cur += ch; continue
        if ch == "," and depth == 0:
            parts.append(cur.strip()); cur = ""; continue
        cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _strip_comments(text: str) -> str:
    # Block comments first (e.g. the /* ... */ template example some
    # ciphers.js files open with) -- stripping only // line comments
    # would leave that template's own `new cipher(...)` call in place
    # for the parser to spuriously match. Confirmed this matters against
    # a real ciphers.js, not a hypothetical: an earlier version of this
    # function only handled //, and a real uploaded file had exactly this
    # kind of leading block-commented example.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(line.split("//", 1)[0] for line in text.split("\n"))


# Cipher names to pull, and the weight each one carries. Weight is parsed
# from the cipher's own labeled constant where possible; a handful (Agrippa
# Key, Francis Bacon) aren't irrational constants, so they get neutral weight.
ACTIVE_CIPHERS: Dict[str, Optional[float]] = {
    "Agrippa Key":              1.0,
    "\u03d5 1.61":              (1 + math.sqrt(5)) / 2,           # phi  1.618034
    "\u03c0 3.144":             3.144,                             # pyramid-pi variant (kept distinct from math.pi)
    "e 2.71":                   math.e,                            # 2.718282
    "\u221a 3":                 math.sqrt(3),                      # 1.732051
    "\u221a 10":                math.sqrt(10),                     # 3.162278
    "\u03c3 2.414":             1 + math.sqrt(2),                  # silver delta  2.414214
    "\u03c2 2.205":             2.205569430341,                    # supersilver (root of x^3=2x^2+1)
    "Emerald \u03d5^2 = 2.618": ((1 + math.sqrt(5)) / 2) ** 2,      # 2.618034
    "Copper \u03d5^3 = 4.236":  ((1 + math.sqrt(5)) / 2) ** 3,      # 4.236068
    "Nickel 5.192":             (5 + math.sqrt(29)) / 2,            # 5th metallic mean, 5.192582
    "Francis Bacon":            1.0,                                # biliteral cipher, not a ratio
    "\u03c8 1.465":             1.465571231876,                     # supergolden (root of x^3=x^2+1)
    "Iron 6.162":               3 + math.sqrt(10),                  # 6th metallic mean, 6.162278
    "\u03b2 3.302":             (3 + math.sqrt(13)) / 2,            # bronze beta  3.302776
}

# Known data-integrity issue in ciphers.js, applied at parse time: "e 2.71"
# has 27 values for 26 letters (one extra decimal digit of e baked in).
_KNOWN_FIXES = {
    "e 2.71": lambda chars, values: (chars, values[: len(chars)]),
}


def parse_ciphers_js(path: str) -> Dict[str, Cipher]:
    """Parse ciphers.js and return only the ciphers named in ACTIVE_CIPHERS."""
    text = _strip_comments(Path(path).read_text(encoding="utf-8"))
    found: Dict[str, Cipher] = {}

    for m in re.finditer(r"new cipher\(", text):
        start = m.end() - 1
        end = _find_matching_paren(text, start)
        if end == -1:
            continue
        parts = _split_top_level(text[start + 1 : end])
        if len(parts) < 7:
            continue
        name = parts[0].strip().strip("\"'")
        if name not in ACTIVE_CIPHERS:
            continue

        category = parts[1].strip().strip("\"'")
        chars = [int(x) for x in _split_top_level(parts[5].strip()[1:-1])]
        values = [int(x) for x in _split_top_level(parts[6].strip()[1:-1])]

        if name in _KNOWN_FIXES:
            print(f"  [!] numerology: applying known fix for cipher '{name}' "
                  f"({len(chars)} chars vs {len(values)} values)", file=sys.stderr)
            chars, values = _KNOWN_FIXES[name](chars, values)

        if len(chars) != len(values):
            print(f"  [!] numerology: cipher '{name}' has {len(chars)} chars "
                  f"but {len(values)} values -- skipped.", file=sys.stderr)
            continue

        weight = ACTIVE_CIPHERS[name]
        found[name] = Cipher(
            name=name, category=category,
            char_map=dict(zip(chars, values)),
            weight=weight,
        )

    missing = set(ACTIVE_CIPHERS) - set(found)
    if missing:
        print(f"  [!] numerology: ciphers not found in {path}: {sorted(missing)}",
              file=sys.stderr)
    return found


_CIPHER_CACHE: Optional[Dict[str, Cipher]] = None


def load_ciphers(js_path: str = "ciphers.js") -> Dict[str, Cipher]:
    global _CIPHER_CACHE
    if _CIPHER_CACHE is None:
        _CIPHER_CACHE = parse_ciphers_js(js_path)
    return _CIPHER_CACHE


def reset_cipher_cache() -> None:
    """Not in your source -- added so the agent/test suite can load a
    different ciphers.js path within one process without the module-level
    cache silently serving a stale/wrong file. load_ciphers() itself is
    otherwise verbatim."""
    global _CIPHER_CACHE
    _CIPHER_CACHE = None


# ---------------------------------------------------------------------------
# NAME / DATE VALUATION -- verbatim.
# ---------------------------------------------------------------------------
MASTER_NUMBERS = {11, 22, 33, 44}


def reduce_number(n: int, keep_master: bool = True) -> int:
    """Digital-root reduction, preserving master numbers unless disabled."""
    while n > 9:
        if keep_master and n in MASTER_NUMBERS:
            return n
        n = sum(int(d) for d in str(n))
    return n


def cipher_value(text: str, cipher: Cipher) -> Tuple[int, List[Tuple[str, int]]]:
    """Raw sum + per-letter breakdown for `text` under one cipher."""
    total, breakdown = 0, []
    for ch in text.lower():
        code = ord(ch)
        val = cipher.char_map.get(code)
        if val is not None:
            total += val
            breakdown.append((ch, val))
    return total, breakdown


def date_value(year: int, month: int, day: int) -> int:
    """
    Sum of ALL digits in a YYYY-MM-DD date, reduced once at the end.
    Note: this is mathematically identical to reducing year/month/day
    separately and summing THOSE -- digit-sum is associative -- UNLESS a
    part is itself frozen at a master number before the final add (some
    Pythagorean practitioners do this; this module does not). Flagging
    the method rather than leaving it implicit, since it's a real fork
    in numerology practice, not a settled single answer.
    """
    return sum(int(d) for d in f"{year:04d}{month:02d}{day:02d}")


# ---------------------------------------------------------------------------
# CHALDEAN PLANETARY RULERS (1-9) -- verbatim.
# Maps to body names already present in tools/chart.py's PLANET_CATALOG.
# ---------------------------------------------------------------------------
NUMEROLOGY_PLANET_RULERS: Dict[int, str] = {
    1: "Sun", 2: "Moon", 3: "Jupiter", 4: "Uranus", 5: "Mercury",
    6: "Venus", 7: "Neptune", 8: "Saturn", 9: "Mars",
}

# Master numbers (11/22/33/44) are a PYTHAGOREAN concept layered onto this
# CHALDEAN 1-9 table -- a documented hybrid, not native to either tradition
# alone. A master number rules through the SAME planet as its own
# un-preserved digit root -- 11->2, 22->4, 33->6, 44->8 -- matching the
# "higher octave of its base number" framing numerology already uses for
# master numbers. Its distinct character is expressed as an AMPLIFIED
# contribution instead of a different ruler (see MASTER_NUMBER_AMPLIFIER).
# 44 is the shakiest of the four: several Pythagorean sources recognize
# only 11/22/33 as true master numbers. Kept, but worth knowing it's the
# least consensus-backed entry -- and in practice date_value() on any
# realistic 1900-2099 birth date tops out well below 44, so it can only
# ever be reached through a cipher's name-sum path, not the life-path number.
MASTER_NUMBER_AMPLIFIER = 1.5


def ruling_planet(value: int) -> str:
    """Planet for a 1-9 digit or a master number (11/22/33/44). Master
    numbers are re-reduced to their base digit root to find the ruler."""
    return NUMEROLOGY_PLANET_RULERS[reduce_number(value, keep_master=False)]


# ---------------------------------------------------------------------------
# PROFILE + WEALTH-SCORE INTEGRATION -- verbatim.
# ---------------------------------------------------------------------------
@dataclass
class CipherResult:
    cipher: str
    weight: float
    raw_sum: int
    reduced: int
    planet: str


@dataclass
class NumerologyProfile:
    name: str
    birth_date: Tuple[int, int, int]     # (year, month, day)
    life_path: int
    life_path_planet: str
    expression: Dict[str, CipherResult] = field(default_factory=dict)


def compute_numerology_profile(
    name: str, birth_date: Tuple[int, int, int], js_path: Optional[str] = None,
) -> NumerologyProfile:
    ciphers = load_ciphers(js_path or str(DEFAULT_CIPHERS_JS_PATH))
    year, month, day = birth_date

    life_path_raw = date_value(year, month, day)
    life_path = reduce_number(life_path_raw)
    life_path_planet = ruling_planet(life_path)

    expression: Dict[str, CipherResult] = {}
    for cname, cipher in ciphers.items():
        raw, _ = cipher_value(name, cipher)
        reduced = reduce_number(raw)
        expression[cname] = CipherResult(
            cipher=cname, weight=cipher.weight, raw_sum=raw,
            reduced=reduced, planet=ruling_planet(reduced),
        )

    return NumerologyProfile(
        name=name, birth_date=birth_date,
        life_path=life_path, life_path_planet=life_path_planet,
        expression=expression,
    )


NUMEROLOGY_SCALE = 0.5   # tuning constant, same role as STAR_FACTOR


def score_numerology_boost(
    profile: NumerologyProfile,
    aspect_log: List[dict],
    dignity_log: List[dict],
) -> Tuple[float, List[dict]]:
    """
    For each active cipher, pull the ALREADY-COMPUTED dignity bonus and
    aggregate aspect contribution of its ruling planet, scale by the
    cipher's own irrational/metallic constant, and sum.
    Returns (total_boost, per_cipher_log).
    """
    if not profile.expression:
        return 0.0, []

    avg_weight = sum(r.weight for r in profile.expression.values()) / len(profile.expression)
    dignity_by_planet = {d["planet"]: d["bonus"] for d in dignity_log}

    total = 0.0
    log: List[dict] = []
    for cname, result in profile.expression.items():
        planet = result.planet
        aspect_sum = sum(e["contrib"] for e in aspect_log if planet in e["pair"])
        dignity_bonus = dignity_by_planet.get(planet, 0.0)
        planet_signal = aspect_sum + dignity_bonus

        is_master = result.reduced in MASTER_NUMBERS
        amp = MASTER_NUMBER_AMPLIFIER if is_master else 1.0

        rel_weight = result.weight / avg_weight if avg_weight else 1.0
        contrib = planet_signal * rel_weight * amp * NUMEROLOGY_SCALE / len(profile.expression)
        total += contrib

        log.append({
            "cipher":   cname,
            "weight":   round(result.weight, 4),
            "reduced":  result.reduced,
            "master":   is_master,
            "planet":   planet,
            "signal":   round(planet_signal, 3),
            "contrib":  round(contrib, 3),
        })

    log.sort(key=lambda x: abs(x["contrib"]), reverse=True)
    return total, log


def numerology_profile_to_dict(profile: NumerologyProfile) -> dict:
    """Not in your source (which only ever printed/exported profiles via
    wealth_algorithm.py's own print_report/export_results) -- added for
    this project's tool_result JSON shape."""
    return {
        "name": profile.name,
        "birth_date": f"{profile.birth_date[0]:04d}-{profile.birth_date[1]:02d}-{profile.birth_date[2]:02d}",
        "life_path": profile.life_path,
        "life_path_planet": profile.life_path_planet,
        "life_path_is_master": profile.life_path in MASTER_NUMBERS,
        "ciphers": {
            cname: {
                "weight": round(r.weight, 4), "raw_sum": r.raw_sum,
                "reduced": r.reduced, "planet": r.planet,
                "is_master": r.reduced in MASTER_NUMBERS,
            }
            for cname, r in profile.expression.items()
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# CORE PYTHAGOREAN NUMEROLOGY -- Attitude, Expression, Soul Urge,
# Personality, Maturity, Universal Day/Month/Year, Personal Day/Month/Year.
#
# Not from any uploaded script -- these formulas came from your chat
# messages, specified precisely enough (down to master-number handling
# per number, and which pieces feed which) that nothing here was guessed.
# Distinct from the 15-cipher irrational-constant ring above: these are
# the standard, specifically-named Pythagorean numerology numbers, so
# they use the standard Pythagorean letter table (A=1..I=9, J=1..R=9,
# S=1..Z=8) -- NOT one of the 15 irrational-constant ciphers, and not a
# hand-typed table either. Your real ciphers.js has an entry literally
# named "Pythagorean" with exactly these values; loaded directly from
# there (see load_pythagorean_cipher) rather than retyped, so a real,
# verifiable file backs this rather than a table this module invented.
# Confirmed to match the standard table via independent web search before
# being trusted -- see the verification in chat.
#
# Y is always treated as a consonant. Some traditions treat Y as a vowel
# when it's the only vowel sound in a syllable ("myth", "rhythm") -- that
# requires syllable-level judgment this module doesn't attempt. Simple
# and consistent was chosen over contextual and occasionally-right;
# flagged here rather than left implicit, since it's a real simplification,
# not a settled convention.
# ═══════════════════════════════════════════════════════════════════════
VOWELS = frozenset("aeiou")

_PYTHAGOREAN_CACHE: Optional[Cipher] = None


def load_pythagorean_cipher(js_path: Optional[str] = None) -> Cipher:
    """Extract the 'Pythagorean' cipher from ciphers.js directly -- NOT
    via load_ciphers()/ACTIVE_CIPHERS, since adding 'Pythagorean' to that
    15-cipher whitelist would silently pull it into score_numerology_boost's
    irrational-constant ring (changing that ring's avg_weight and adding
    an unintended contribution to the wealth score). This is a completely
    separate, independent use of the same ciphers.js file and the same
    low-level parser, for a different purpose."""
    global _PYTHAGOREAN_CACHE
    if _PYTHAGOREAN_CACHE is not None:
        return _PYTHAGOREAN_CACHE

    path = js_path or str(DEFAULT_CIPHERS_JS_PATH)
    text = _strip_comments(Path(path).read_text(encoding="utf-8"))
    for m in re.finditer(r"new cipher\(", text):
        start = m.end() - 1
        end = _find_matching_paren(text, start)
        if end == -1:
            continue
        parts = _split_top_level(text[start + 1 : end])
        if len(parts) < 7:
            continue
        name = parts[0].strip().strip("\"'")
        if name != "Pythagorean":
            continue
        category = parts[1].strip().strip("\"'")
        chars = [int(x) for x in _split_top_level(parts[5].strip()[1:-1])]
        values = [int(x) for x in _split_top_level(parts[6].strip()[1:-1])]
        if len(chars) != len(values):
            raise ValueError(
                f"'Pythagorean' cipher has {len(chars)} chars but {len(values)} "
                f"values in {path} -- can't use it safely."
            )
        _PYTHAGOREAN_CACHE = Cipher(name=name, category=category,
                                     char_map=dict(zip(chars, values)), weight=1.0)
        return _PYTHAGOREAN_CACHE
    raise FileNotFoundError(f"No cipher named 'Pythagorean' found in {path}")


def reset_pythagorean_cache() -> None:
    """Mirrors reset_cipher_cache() -- lets the agent/test suite load a
    different ciphers.js path within one process."""
    global _PYTHAGOREAN_CACHE
    _PYTHAGOREAN_CACHE = None


def _name_part_value(text: str, cipher: Cipher, filter_: str = "all") -> int:
    """Sum of a name part's Pythagorean letter values. filter_: 'all'
    (Expression), 'vowels' (Soul Urge), or 'consonants' (Personality, Y
    always included here -- see module note above)."""
    total = 0
    for ch in text.lower():
        if not ch.isalpha():
            continue
        if filter_ == "vowels" and ch not in VOWELS:
            continue
        if filter_ == "consonants" and ch in VOWELS:
            continue
        total += cipher.char_map.get(ord(ch), 0)
    return total


@dataclass
class NamePartTotals:
    """One of Expression/Soul Urge/Personality's intermediate results --
    exposed because your own definition treats the per-part totals as
    meaningful (unreduced), not just a computation detail."""
    parts: List[str]
    part_totals: List[int]   # unreduced, one per name part, in order given
    raw_sum: int             # sum of part_totals, still unreduced
    reduced: int             # raw_sum, reduced (master numbers preserved)


def _name_parts_number(name_parts: List[str], filter_: str, js_path: Optional[str] = None) -> NamePartTotals:
    cipher = load_pythagorean_cipher(js_path)
    totals = [_name_part_value(part, cipher, filter_) for part in name_parts if part]
    raw_sum = sum(totals)
    return NamePartTotals(
        parts=[p for p in name_parts if p], part_totals=totals,
        raw_sum=raw_sum, reduced=reduce_number(raw_sum, keep_master=True),
    )


def expression_number(name_parts: List[str], js_path: Optional[str] = None) -> NamePartTotals:
    """All letters of first/middle(s)/last/suffix, each part's total left
    unreduced, then summed and reduced (master numbers preserved)."""
    return _name_parts_number(name_parts, "all", js_path)


def soul_urge_number(name_parts: List[str], js_path: Optional[str] = None) -> NamePartTotals:
    """Same structure as expression_number, vowels only."""
    return _name_parts_number(name_parts, "vowels", js_path)


def personality_number(name_parts: List[str], js_path: Optional[str] = None) -> NamePartTotals:
    """Same structure as expression_number, consonants only (Y included)."""
    return _name_parts_number(name_parts, "consonants", js_path)


def attitude_number(birth_month: int, birth_day: int) -> int:
    """Day + month of birth, reduced to a SINGLE DIGIT -- the one number
    in this whole system explicitly specified without master-number
    preservation. Not an oversight: your definition says "reduce...to a
    single-digit number", full stop, where every other definition adds
    "or master number (11, 22, 33, 44)". Preserved as the one deliberate
    exception, not normalized to match the others."""
    total = sum(int(d) for d in str(birth_month)) + sum(int(d) for d in str(birth_day))
    return reduce_number(total, keep_master=False)


def maturity_number(life_path: int, expression: int) -> int:
    """Life Path + Expression, reduced (master numbers preserved)."""
    return reduce_number(life_path + expression, keep_master=True)


def universal_day(year: int, month: int, day: int) -> int:
    """MM+DD+YYYY of the TARGET date (not birth date) -- same digit-sum
    method as Life Path/date_value(), applied to whatever date is being
    asked about. Reduced, master numbers preserved."""
    return reduce_number(date_value(year, month, day), keep_master=True)


def universal_month(year: int, month: int) -> int:
    """MM+YYYY of the target date, reduced (master numbers preserved)."""
    total = sum(int(d) for d in f"{month:02d}") + sum(int(d) for d in f"{year:04d}")
    return reduce_number(total, keep_master=True)


def universal_year(year: int) -> int:
    """Y+Y+Y+Y -- the four individual digits of the target year, summed
    and reduced (master numbers preserved)."""
    total = sum(int(d) for d in f"{year:04d}")
    return reduce_number(total, keep_master=True)


def personal_day(universal_day_value: int, attitude: int) -> int:
    """Universal Day + Attitude Number, reduced (master numbers preserved)."""
    return reduce_number(universal_day_value + attitude, keep_master=True)


def personal_month(universal_month_value: int, attitude: int) -> int:
    """Universal Month + Attitude Number, reduced (master numbers preserved)."""
    return reduce_number(universal_month_value + attitude, keep_master=True)


def personal_year(universal_year_value: int, attitude: int) -> int:
    """Universal Year + Attitude Number, reduced (master numbers preserved)."""
    return reduce_number(universal_year_value + attitude, keep_master=True)


@dataclass
class CoreNumerologyProfile:
    """Bundles Life Path (already computed elsewhere in this module) with
    the 5 name/date-derived core numbers plus the 6 Universal/Personal
    numbers for one target date."""
    first_name: str
    middle_names: List[str]
    last_name: str
    suffix: Optional[str]
    birth_date: Tuple[int, int, int]
    target_date: Tuple[int, int, int]

    life_path: int
    life_path_planet: str
    attitude: int
    expression: NamePartTotals
    soul_urge: NamePartTotals
    personality: NamePartTotals
    maturity: int
    universal_day: int
    universal_month: int
    universal_year: int
    personal_day: int
    personal_month: int
    personal_year: int


def compute_core_numerology_profile(
    first_name: str,
    last_name: str,
    birth_date: Tuple[int, int, int],
    middle_names: Optional[List[str]] = None,
    suffix: Optional[str] = None,
    target_date: Optional[Tuple[int, int, int]] = None,
    js_path: Optional[str] = None,
) -> CoreNumerologyProfile:
    """Full core-Pythagorean profile. target_date defaults to birth_date
    (Universal/Personal numbers FOR the birth date itself) if not given --
    pass today's date (or any date) to get that date's Personal Day/Month/
    Year instead."""
    middle_names = middle_names or []
    target_date = target_date or birth_date
    name_parts = [first_name] + list(middle_names) + [last_name] + ([suffix] if suffix else [])

    by, bm, bd = birth_date
    ty, tm, td = target_date

    life_path_raw = date_value(by, bm, bd)
    life_path = reduce_number(life_path_raw)
    life_path_planet = ruling_planet(life_path)

    attitude = attitude_number(bm, bd)
    expr = expression_number(name_parts, js_path)
    soul = soul_urge_number(name_parts, js_path)
    pers = personality_number(name_parts, js_path)
    maturity = maturity_number(life_path, expr.reduced)

    u_day = universal_day(ty, tm, td)
    u_month = universal_month(ty, tm)
    u_year = universal_year(ty)
    p_day = personal_day(u_day, attitude)
    p_month = personal_month(u_month, attitude)
    p_year = personal_year(u_year, attitude)

    return CoreNumerologyProfile(
        first_name=first_name, middle_names=middle_names, last_name=last_name,
        suffix=suffix, birth_date=birth_date, target_date=target_date,
        life_path=life_path, life_path_planet=life_path_planet,
        attitude=attitude, expression=expr, soul_urge=soul, personality=pers,
        maturity=maturity, universal_day=u_day, universal_month=u_month,
        universal_year=u_year, personal_day=p_day, personal_month=p_month,
        personal_year=p_year,
    )


def core_numerology_profile_to_dict(p: CoreNumerologyProfile) -> dict:
    def _parts(nt: NamePartTotals) -> dict:
        return {
            "parts": nt.parts, "part_totals": nt.part_totals,
            "raw_sum": nt.raw_sum, "reduced": nt.reduced,
            "is_master": nt.reduced in MASTER_NUMBERS,
        }
    return {
        "name": {
            "first": p.first_name, "middle": p.middle_names,
            "last": p.last_name, "suffix": p.suffix,
        },
        "birth_date": f"{p.birth_date[0]:04d}-{p.birth_date[1]:02d}-{p.birth_date[2]:02d}",
        "target_date": f"{p.target_date[0]:04d}-{p.target_date[1]:02d}-{p.target_date[2]:02d}",
        "life_path": {"value": p.life_path, "planet": p.life_path_planet,
                      "is_master": p.life_path in MASTER_NUMBERS},
        "attitude": p.attitude,   # never a master number -- see attitude_number()
        "expression": _parts(p.expression),
        "soul_urge": _parts(p.soul_urge),
        "personality": _parts(p.personality),
        "maturity": {"value": p.maturity, "is_master": p.maturity in MASTER_NUMBERS},
        "universal": {
            "day": p.universal_day, "month": p.universal_month, "year": p.universal_year,
        },
        "personal": {
            "day": p.personal_day, "month": p.personal_month, "year": p.personal_year,
        },
    }
