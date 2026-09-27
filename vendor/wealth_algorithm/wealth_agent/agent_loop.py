"""
agent_loop.py — Tool-calling loop against the Anthropic API for the
wealth scoring agent.

FRAMEWORK NOTE: your uploaded wealth_algorithm.py defaults to TROPICAL
and takes --sidereal to opt in. Per your standing instruction for this
project, get_natal_chart is ALWAYS called with sidereal=True here --
never exposed as a choice to the model. The system prompt below
reinforces this in the model's own language too.

Tracked bodies (matching your source exactly): Sun, Moon, Mercury, Venus,
Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, True Black Moon Lilith (11
"planets") + Lot of Fortune, Lot of Spirit, White Moon Selena (3 computed
points), plus 30 fixed stars/deep-space points. Chiron is NOT a tracked/scored body -- see
calendar_bridge.py's COSMIC_MONTH_RULERS note for how Ophiuchus's
traditional-ruler label is handled.

64-GATE HUMAN DESIGN LAYER: three more tools (get_gate_for_longitude,
get_chart_gates, get_day_gate) overlay the I Ching/periodic-table gate
wheel on the same sidereal ring, and score_wealth's boost pipeline gained
a third tier (day-gate resonance, x1.15) alongside the existing
month-ruler and suit-element boosts. HOUSE FIELDS ARE CURRENTLY None
EVERYWHERE: the uploaded wealth_algorithm.py has no house system despite
one being described in an accompanying README -- see tools/gates.py's
module docstring for exactly what to fix once the real file arrives.

TYPOLOGY LAYER (Enneagram + MBTI): get_natal_chart takes two more optional
fields (enneagram_type, mbti_type) -- GIVEN/self-reported, never computed,
same as birth data itself. score_wealth's boost pipeline gained a fourth
tier (typology resonance) that fires only when at least one was provided.
See tools/typology.py's module docstring for real data-quality caveats in
the source material (two AI-generated reference images that disagree with
each other and with the typed correspondence tables in several places).

MAYAN TZOLKIN LAYER: two more tools (get_mayan_sign, get_mayan_tree_of_life)
look up the 260-day Tzolkin reading (Day Sign, Galactic Tone, Trecena,
Kin number) for any date, purely from the date -- no time or location
needed, unlike a chart. Deliberately NOT wired into score_wealth's boost
pipeline: unlike Gates or Typology, there's no source-grounded mapping
from a Tzolkin day sign to a specific tracked body/planet to check
resonance against, and inventing one would mean fabricating a whole
correspondence table with zero textual basis, not constructing a
reasonable interpretation of something described. See
tools/mayan_calendar.py's module docstring for exactly what's verified
(the core Tzolkin math, against three independent reference dates) vs.
constructed (the Tree of Life's past/future/masculine/feminine positions,
since the source material describes the concept but never discloses the
formula).

NUMEROLOGY LAYER: get_natal_chart takes one more optional field,
numerology_name -- GIVEN, same as enneagram_type/mbti_type. Unlike every
other layer in this project, this one is wired EXACTLY the way your own
wealth_algorithm.py does it: score_wealth's numerology boost is ADDITIVE,
folded into the raw score BEFORE normalization (raw = aspects + dignities
+ numerology), not a multiplier on the normalized 0-100 score like the
Calendar/Gate/Typology tiers. MISSING DEPENDENCY: ciphers.js (the actual
15-cipher letter-value table) was not included in this upload -- the
engine is fully ported and verified (see tools/numerology.py's module
docstring for exactly how), but produces nothing without that file
present. If numerology_name is given and ciphers.js isn't found, say so
plainly and continue without that tier -- exactly what wealth_algorithm.py
itself does, never silently substitute invented cipher values.

COSMIC PLAYING CARDS + TAROT: get_cosmic_cards works from a date alone
(birth_date or any other date), deriving the Earth card from the Cosmic
Calendar and the other 14 "planetary" cards (Sun, Karma, Moon, Mercury...
Phoenix) from tools/cardology.py's Master Spirit/Life spreads, plus their
Tarot equivalents from tools/tarot.py. Deliberately NOT wired into
score_wealth at all, in either direction (no multiplier tier, no additive
term) -- this matches wealth_algorithm.py's own source exactly, which
computes and reports these purely for display and says so explicitly in
a comment. Don't invent a scoring mechanic for this even if asked "how
much is my card worth" -- say plainly that these are descriptive, not
scored, per the source design.

ASTROCARTOGRAPHY: get_astrocartography_lines takes birth date/time only
(no location -- that's the point: birth time is fixed, location is what
the lines solve for) and returns MC/IC/AC/DC world-map lines for each of
the 10 classical/modern planets. INDEPENDENT OF SIDEREAL/TROPICAL --
these lines come from true equatorial position (right ascension/
declination), real physical geometry that doesn't change based on which
zodiac framework labels it, so don't describe this feature as sidereal or
tropical either way. NOT wired into score_wealth (no source script exists
for this feature to check that against, and no reason to assume one
should be invented). AC/DC lines can have real gaps at latitudes where a
body is circumpolar (never rises/sets there) -- report those as gaps, not
as a missing/broken result. See tools/astrocartography.py's module
docstring for how this was verified (an independent solver cross-check,
not just internal consistency) and for a real topocentric-parallax bug
the verification caught and fixed for the Moon specifically.

render_astrocartography_map writes a static world-map image (PNG/SVG) to
disk and returns its path. render_interactive_astrocartography_map writes
a single self-contained HTML file (pan/zoom, per-planet show/hide via a
layer control, hover tooltips) -- this WAS the "no way to verify an
HTML+JS map before shipping it" limitation noted in an earlier version of
this project, resolved by getting a headless browser working in the
sandbox this was built in (Playwright's Chromium) specifically so every
generated map could be, and was, actually opened, rendered, and
screenshotted -- including clicking the layer-control checkboxes and
confirming lines actually appear/disappear, not just that the page loads
without a JS error. See tools/astrocartography_interactive.py's module
docstring for what that verification covered. Both map tools only return
a file path -- tell the person where to find it, since neither tool
displays the image/page itself.

Run from inside the wealth_agent/ directory: `python agent_loop.py`
Requires: ANTHROPIC_API_KEY environment variable set to a real key.
"""

from __future__ import annotations

import json
import os
from datetime import date as _date
from typing import Any, Dict, Optional

import anthropic

from tools.chart import (
    get_natal_chart, chart_to_dict, NatalChart,
    PLANET_CATALOG, COMPUTED_WEIGHTS,
)
from tools.scoring import (
    score_wealth, score_result_to_dict,
    score_aspects, score_dignities, finalize_wealth_score,
)
from tools.calendar_bridge import cosmic_day_to_date, date_to_cosmic_day, SUIT_SYMBOL
from tools.gate_calendar_bridge import apply_all_cosmic_boosts
from tools.gates import (
    handle_get_gate_for_longitude,
    handle_get_chart_gates,
    handle_get_day_gate,
)
from tools.typology import (
    bodies_to_archetype_wheel,
    apply_typology_boost,
    ENNEAGRAM_CORE,
    MBTI_CONSTELLATIONS,
    MBTI_BY_CONSTELLATION,
    VALID_MBTI_CODES,
    parse_enneagram_input,
    parse_mbti_input,
)
from tools.mayan_calendar import date_to_tzolkin, tree_of_life
from tools.numerology import (
    compute_numerology_profile,
    score_numerology_boost,
    numerology_profile_to_dict,
    ciphers_js_available,
    DEFAULT_CIPHERS_JS_PATH,
    compute_core_numerology_profile,
    core_numerology_profile_to_dict,
)
from tools import cardology
from tools import tarot
from tools.astrocartography import compute_lines, body_lines_to_dict, ACG_BODIES, DEFAULT_LAT_STEP
from tools.astrocartography_map import render_map
from tools.astrocartography_interactive import render_interactive_map
from cache import ChartCache

_SUIT_SYMBOL_TO_LETTER: Dict[str, str] = {v: k[0].upper() for k, v in SUIT_SYMBOL.items()}
# {'♠': 'S', '♦': 'D', '♣': 'C', '♥': 'H'}


MODEL = "claude-sonnet-5"
MAX_TOKENS = 2048
MAX_TOOL_ITERATIONS = 8  # safety valve against runaway tool-call loops

SYSTEM_PROMPT = """You are a wealth-scoring astrology agent built on the user's \
own wealth_algorithm.py and cosmic_calendar.py. Operate strictly under TRUE \
SIDEREAL astrology -- Lahiri ayanamsa, 13-sign zodiac including Ophiuchus \
-- per the Capricorn Prometheus Software framework. Never describe \
placements in tropical terms.

Tracked bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, \
Neptune, Pluto, True Black Moon Lilith, Lot of Fortune, Lot of Spirit, \
White Moon Selena, plus 30 fixed stars/deep-space points (incl. Galactic \
Center, Super Galactic Center, and the Solar Apex). Chiron, Rahu (mean \
North Node), and Ketu (mean South Node) are ALSO now tracked, but only \
for dignity evaluation and sign/house placement -- NOT for aspects. They \
deliberately don't appear in aspect_log or get an aspect orb weight: \
adding them to full aspect scoring would mean inventing a weight with no \
grounding, a bigger change than what was asked for. If asked "what aspects \
does Chiron make," say plainly that Chiron/Rahu/Ketu aren't part of aspect \
scoring, only dignity -- don't compute aspects for them on the fly.

Custom rulerships: Venus rules Virgo, Mercury rules Libra (in addition to \
their traditional signs). Aspects include three metallic-ratio angles \
(Golden, Silver, Bronze) alongside the standard set -- a single pair of \
bodies CAN trigger more than one aspect simultaneously if orbs overlap; \
that's expected, not a bug to paper over.

DIGNITY SYSTEM covers all 15 bodies above (10 classical/modern + Chiron/ \
Rahu/Ketu/True BML/White Moon Selena) -- domicile, exaltation, detriment, \
fall for each, feeding score_wealth's dig_bonus automatically via \
score_dignities. Mercury/Venus/Neptune's exaltations (Aquarius/Capricorn/ \
Cancer) differ from traditional Western astrology (Virgo/Pisces/Leo) -- \
this is intentional, part of this system's own framework, not an error to \
correct if asked. Chiron/Rahu/Ketu/True BML/White Moon Selena's dignities \
are explicitly "functional/esoteric" rulerships within this custom system, \
not universally recognized ones -- say so if asked, don't present them as \
traditional astrology. SIGN_DIGNITY_ARCHITECTURE (tools/scoring.py) gives \
each sign's notable dignity placements for quick reference -- Ophiuchus's \
entry ("Serpent Gate / Transmutation") is thematic, not a derived dignity \
(no body has any dignity in Ophiuchus in this system).

HOUSE SYSTEM: whole-sign houses, House 1 = Sagittarius (matching the \
Cosmic Calendar's own year start, not the traditional Aries start), \
House 12 covering both Scorpio and Ophiuchus. Every body's "house" field \
now populates for real (a gap in earlier versions of this project is \
resolved) -- present it plainly, it's not a placeholder.

Always call get_natal_chart before score_wealth for a new person -- \
score_wealth reads the previously stored chart by label rather than \
taking birth data directly. Use recall_chart / list_recalled_charts when \
a user references someone already computed this session.

64-Gate Human Design layer: every body's sidereal longitude also maps to \
one of 64 Gates (I Ching hexagram, keyed to the chemical element sharing \
its atomic number) via get_chart_gates / get_gate_for_longitude / \
get_day_gate. This is an independent overlay on the same sidereal ring as \
the 13-sign constellations -- a body's Gate and its constellation don't \
share a boundary edge, by design, so report both without trying to \
reconcile them into one system. score_wealth's boost pipeline includes a \
day-gate tier (x1.15): unlike the month-ruler and suit-element tiers \
(both evaluated at the chart's own birth date), the day-gate tier compares \
the chart against the Sun's CURRENTLY TRANSITING Gate by default -- it's a \
"does this chart resonate with today" check, not a birth-data check.

Enneagram/MBTI typology: GIVEN facts the person states about themselves -- \
never infer, guess, or compute one. If neither is stated, don't bring the \
topic up unprompted (outside the startup prompt in main.py's agent mode, \
which asks once upfront). ACCEPTED FORMATS, exact: Enneagram is "7w8" \
(core+wing, wing must be numerically adjacent to the core -- type 7 can \
only wing to 6 or 8) or "9" (core only) or "N/A"; MBTI is "INTJ-A"/"INTJ-T" \
(code+Assertive/Turbulent) or "INTJ" (code only) or "N/A". Reject/re-ask on \
anything else rather than guessing what was meant -- get_natal_chart's \
error message states exactly what's wrong (e.g. a non-adjacent wing) so \
relay that back rather than paraphrasing. Wing and A/T variant are stored \
(enneagram_wing, mbti_variant) but NOT scored -- no resonance mechanic was \
specified for them, only for the core type/code, so score_wealth's typology \
boost still runs off enneagram_type/mbti_type alone. When at least the core \
is stated, score_wealth automatically checks it for resonance (a four-tier \
boost, after month-ruler/suit-element/day-gate): does the type's ruling \
planet show up active in the chart, and does any tracked body sit in one \
of the type's constellations on a separate, independent 13-constellation \
wheel (Sagittarius=0 sidereal degrees -- NOT the same boundaries as the \
regular 13-sign chart, by design, the same way the Gate wheel doesn't \
share edges with it either). The source data for this wheel has real gaps \
and inconsistencies between its two reference images -- if asked why a \
specific cell looks off, say so plainly rather than smoothing over it.

Mayan Tzolkin: get_mayan_sign and get_mayan_tree_of_life work from a date \
alone (birth_date, today, or any other date) -- no chart needed, and \
NOT wired into score_wealth's boost pipeline (there's no source-grounded \
day-sign-to-planet correspondence to check resonance against, unlike \
Gates or Typology). The core reading (Day Sign, Tone, Trecena, Kin) is \
verified Tzolkin math -- present it plainly. The Tree of Life's four \
outer positions (past/future/masculine/feminine) are explicitly a \
constructed interpretation, not verified against any real source -- say \
so if asked, don't present them with the confidence of the center reading.

Core Pythagorean numerology (get_core_numerology_profile): Life Path, \
Attitude, Expression, Soul Urge, Personality, Maturity, plus Universal \
Day/Month/Year and Personal Day/Month/Year for a target date. Distinct \
from get_numerology_profile's 15-cipher irrational-constant ring (which \
stays wired into score_wealth's additive boost, unchanged) -- this one \
uses the standard Pythagorean letter table and is NOT wired into \
score_wealth at all; report it descriptively. Every number reduces to a \
single digit OR a master number (11/22/33/44) EXCEPT Attitude, which \
reduces to a single digit only, by design -- don't "correct" an \
unreduced-looking Attitude value that happens to be e.g. 11. Ask for \
first/last name (middle names and suffix optional) and birth date; \
target_date defaults to birth_date if not given -- offer to use today's \
date for "what's my personal year right now"-type questions.

Numerology: numerology_name on a chart is GIVEN, same as enneagram_type/ \
mbti_type -- ask, don't infer. Unlike every other boost tier, numerology's \
is ADDITIVE and pre-normalization (mirrors your own wealth_algorithm.py's \
main() exactly: raw = aspects + dignities + numerology, then normalize), \
not a multiplier on the final 0-100 score. It requires ciphers.js, which \
is NOT currently available -- score_wealth and get_numerology_profile \
both return a plain, specific error/note when it's missing rather than a \
fabricated result. If a person asks for their numerology and it's \
unavailable, say exactly that (missing cipher data file) rather than \
producing a plausible-sounding profile from general numerology knowledge \
-- this project's numerology tier is specifically the 15-cipher irrational- \
constant ring from tools/numerology.py, not generic numerology.

Cosmic Playing Cards + Tarot: get_cosmic_cards works from a date alone \
(birth_date or any other date) -- Earth card plus 14 derived cards (Sun, \
Karma, Moon, Mercury...Phoenix) with their Tarot equivalents. NEVER \
folded into score_wealth, in either direction -- no multiplier, no \
additive term. This matches your own wealth_algorithm.py exactly, which \
computes and displays these purely for reading and says so in its own \
comments. If asked "how much is my card worth" or similar, say plainly \
these are descriptive, not scored -- don't improvise a scoring rule.

Astrocartography: get_astrocartography_lines takes birth date/time ONLY \
-- no location, since location is what these lines solve for, not an \
input to them. Independent of sidereal/tropical (true equatorial \
position, real physical geometry -- don't frame this as either). AC/DC \
curves can have genuine gaps at latitudes where a planet is circumpolar \
there (never crosses the horizon) -- these are real astronomy, not \
missing data; explain them as such if asked, don't paper over a gap by \
interpolating across it. NOT scored, same relationship as Cosmic Cards \
and Mayan astrology have to score_wealth. This is coordinate data (a \
list of points per line) -- when explaining results, describe the \
notable named places each line passes near rather than reciting raw \
coordinates, since that's what actually makes an ACG reading useful \
to a person. When a person wants to SEE their lines rather than just \
hear about them, use render_interactive_astrocartography_map by default \
(pan/zoom, toggle individual planets, hover tooltips -- genuinely more \
usable than a fixed image once more than 2-3 planets are shown at once); \
use render_astrocartography_map (static PNG/SVG) instead only if they \
specifically want a plain image file, e.g. to paste elsewhere. Both only \
return a file path -- tell them where to find it and to open it in a \
browser, since you can't display it yourself.

The final normalized_score (0-100) comes with a rating label (Exceptional \
/ Strong / Moderate / Developing / Challenging) -- use it, don't invent \
your own tier language. After tool results come back, always finish with \
a short plain-language interpretation -- never leave raw JSON as the \
final answer, and don't dump the entire aspect_log; mention only the \
handful of strongest contributors (already sorted by |contrib| descending).

If a tool result contains an "errors" or "error" field, name the specific \
issue in your reply instead of glossing over it or inventing a value to \
fill the gap."""

TOOLS = [
    {
        "name": "get_natal_chart",
        "description": (
            "Compute a true sidereal (Lahiri) natal chart -- all 11 "
            "tracked planets/points, 3 computed points (Lots + Selena), "
            "30 fixed stars/deep-space points, ascendant, and day/night status -- and store "
            "it under a label for later recall. Always call this before "
            "score_wealth for a new person. enneagram_type/mbti_type are "
            "GIVEN facts the person states about themselves (never inferred "
            "or computed) -- ask if the person wants typology resonance "
            "included but don't guess a value they haven't stated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
                "birth_time": {"type": "string", "description": "HH:MM or HH:MM:SS, 24hr, in UT"},
                "latitude": {"type": "number", "description": "N positive, S negative"},
                "longitude": {"type": "number", "description": "E positive, W negative"},
                "label": {
                    "type": "string",
                    "description": "Short handle to recall this chart later, e.g. 'self' or 'partner'.",
                },
                "enneagram_type": {
                    "type": "string",
                    "description": (
                        "Optional. The person's self-known Enneagram type. Formats: "
                        "'7w8' (core + wing, wing must be numerically adjacent to the "
                        "core), '9' (core only, wing unknown), or 'N/A' if they don't "
                        "know their type. Omit entirely only if not asked yet."
                    ),
                },
                "mbti_type": {
                    "type": "string",
                    "description": (
                        "Optional. The person's self-known MBTI type. Formats: "
                        "'INTJ-A' or 'INTJ-T' (4-letter code + Assertive/Turbulent, "
                        "if known), 'INTJ' (code only), or 'N/A' if they don't know "
                        "their type. Omit entirely only if not asked yet."
                    ),
                },
                "numerology_name": {
                    "type": "string",
                    "description": (
                        "Optional. Name to run through the numerology cipher ring "
                        "(may differ from the chart label, e.g. a full legal name). "
                        "Omit to skip the numerology tier. Currently non-functional "
                        "without ciphers.js -- see system prompt."
                    ),
                },
            },
            "required": ["birth_date", "birth_time", "latitude", "longitude", "label"],
        },
    },
    {
        "name": "score_wealth",
        "description": (
            "Compute the normalized 0-100 wealth score (+ rating label) "
            "for a previously computed chart (by label): planet-planet and "
            "planet-star aspects (14 types incl. metallic-ratio angles), "
            "dignity/debility bonuses, and three automatic boosts -- Cosmic "
            "Calendar month-ruler / suit-element (from the chart's own "
            "birth date) plus a day-gate resonance boost (from as_of_date, "
            "default today)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Label used in get_natal_chart"},
                "as_of_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD. Date the day-gate transit boost is evaluated at. Defaults to today if omitted.",
                },
            },
            "required": ["label"],
        },
    },
    {
        "name": "cosmic_day_to_date",
        "description": "Forward lookup: cosmic (year label, month 1-13, day 1-28) -> Gregorian date + playing card.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cosmic_year": {"type": "integer", "description": "Cosmic year LABEL, e.g. 2026 = Dec 2025 - Dec 2026"},
                "month": {"type": "integer", "description": "1-13"},
                "day_in_month": {"type": "integer", "description": "1-28"},
            },
            "required": ["cosmic_year", "month", "day_in_month"],
        },
    },
    {
        "name": "date_to_cosmic_day",
        "description": (
            "Reverse lookup: Gregorian date -> cosmic year/month/day + "
            "playing card. Correctly handles the Leap/Joker Day (Dec 18) "
            "and the intercalary Feb 29 (7 of Diamonds) as explicit cases."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gregorian_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["gregorian_date"],
        },
    },
    {
        "name": "recall_chart",
        "description": "Retrieve a previously computed chart by label without recomputing it.",
        "input_schema": {
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
    },
    {
        "name": "list_recalled_charts",
        "description": "List labels of all charts computed so far this session.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_gate_for_longitude",
        "description": (
            "Resolve a single sidereal (Lahiri) ecliptic longitude to its "
            "64-Gate Human Design placement: Gate, Line (1-6), the gate's "
            "keyed chemical element, and I Ching hexagram. Use for a "
            "quick one-off lookup when a longitude is already known -- no "
            "chart computation involved."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sidereal_longitude": {
                    "type": "number",
                    "description": "Sidereal ecliptic longitude in decimal degrees, 0-360.",
                },
            },
            "required": ["sidereal_longitude"],
        },
    },
    {
        "name": "get_chart_gates",
        "description": (
            "Compute the full 64-Gate placement (Gate, Line, element, "
            "hexagram, 13-sign sidereal constellation) for all 14 tracked "
            "bodies in a birth or transit chart. This is an independent "
            "overlay on the same sidereal ring as get_natal_chart's "
            "constellations -- the two don't share a boundary edge by "
            "design. House is currently always null (see system prompt)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "birth_date": {"type": "string", "description": "YYYY-MM-DD (UTC)"},
                "birth_time": {"type": "string", "description": "HH:MM:SS (UTC). Defaults to 12:00:00 if omitted."},
                "latitude": {"type": "number", "description": "N positive, S negative"},
                "longitude": {"type": "number", "description": "E positive, W negative"},
                "name": {"type": "string", "description": "Optional label for the native/chart."},
            },
            "required": ["birth_date", "latitude", "longitude"],
        },
    },
    {
        "name": "get_day_gate",
        "description": (
            "Get the 'Day Gate' for a civil date -- the Gate and Line the "
            "Sun sidereally occupies that day, plus the cosmic_calendar "
            "playing card for context. This is the same value score_wealth's "
            "day-gate boost tier compares a chart's own Gates against."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "YYYY-MM-DD. Defaults to today (UTC) if omitted.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_typology_info",
        "description": (
            "Look up an Enneagram type or MBTI code's planetary/"
            "constellation correspondences on the rebased (Sagittarius=0) "
            "wheel -- no chart needed. Use for a quick explanation ('what "
            "does INTJ correspond to') separate from checking resonance "
            "against an actual chart, which score_wealth does automatically "
            "once a chart has enneagram_type/mbti_type stored."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enneagram_type": {"type": "integer", "description": "1-9"},
                "mbti_type": {"type": "string", "description": "4-letter MBTI code"},
            },
            "required": [],
        },
    },
    {
        "name": "get_mayan_sign",
        "description": (
            "Look up the 260-day Tzolkin reading for a civil date -- Day "
            "Sign, Galactic Tone, Trecena, and Kin number. Purely a "
            "function of the date, no time or location needed. Use "
            "birth_date for a person's own Mayan sign, or any other date "
            "for the day's current energy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "get_mayan_tree_of_life",
        "description": (
            "The 5-position Tree of Life for a date: center (that date's "
            "own Tzolkin reading) plus past/future/masculine/feminine. "
            "IMPORTANT: only 'center' is verified Tzolkin math -- the four "
            "surrounding positions are a constructed interpretation (the "
            "source material never discloses the actual formula). Say so "
            "if asked, don't present them with the same confidence as center."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "get_numerology_profile",
        "description": (
            "Compute a standalone numerology profile (life path number + "
            "all 15 active ciphers) for a name and birth date, without "
            "needing a full chart or running score_wealth. Requires "
            "ciphers.js to be present -- if it returns an error about a "
            "missing file, say so plainly rather than estimating or "
            "inventing cipher values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name to run through the cipher ring"},
                "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["name", "birth_date"],
        },
    },
    {
        "name": "get_core_numerology_profile",
        "description": (
            "Compute the core Pythagorean numerology profile: Life Path, "
            "Attitude, Expression, Soul Urge, Personality, and Maturity "
            "numbers from a person's name and birth date, plus Universal "
            "Day/Month/Year and Personal Day/Month/Year for a target date "
            "(defaults to the birth date if target_date is omitted -- pass "
            "today's date, or any date, for that date's cycle numbers "
            "instead). Distinct from get_numerology_profile's 15-cipher "
            "irrational-constant ring -- this uses the standard Pythagorean "
            "letter table specifically. Requires ciphers.js (that table is "
            "read from a real cipher named 'Pythagorean' in the same file)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "middle_names": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Optional. Zero or more middle names, in order.",
                },
                "suffix": {"type": "string", "description": "Optional. Jr, III, etc."},
                "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
                "target_date": {
                    "type": "string",
                    "description": "Optional. YYYY-MM-DD. Defaults to birth_date if omitted.",
                },
            },
            "required": ["first_name", "last_name", "birth_date"],
        },
    },
    {
        "name": "get_cosmic_cards",
        "description": (
            "Full Cosmic Playing Card reading for a date -- Earth card plus "
            "the 14 derived 'planetary' cards (Sun, Karma, Moon, Mercury... "
            "Phoenix) from the Master Spirit/Life spreads, each with its "
            "Tarot equivalent. Works from a date alone, no chart needed. "
            "NOT scored -- purely descriptive, matching wealth_algorithm.py's "
            "own design. Returns a plain note (not an error) if the date "
            "falls on the cosmic Leap/Joker Day, which has no card profile."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "get_astrocartography_lines",
        "description": (
            "Astrocartography world-map lines (Jim Lewis AC*G system) for "
            "a birth date/time -- NO location needed, that's what the lines "
            "solve for. Returns, per planet, the MC/IC meridian longitudes "
            "and AC/DC curves (rising/setting lines) as lists of "
            "(longitude, latitude) points. AC/DC curves can have real gaps "
            "at latitudes where the planet is circumpolar there (never "
            "rises/sets) -- present those as gaps, not errors. NOT scored. "
            "Independent of sidereal/tropical -- don't frame it either way."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
                "birth_time": {"type": "string", "description": "HH:MM or HH:MM:SS, 24hr, in UT"},
                "bodies": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Optional. Subset of planet names to compute (default: all 10).",
                },
                "lat_step": {
                    "type": "number",
                    "description": f"Optional. Degrees between AC/DC curve points (default {DEFAULT_LAT_STEP}). Smaller = smoother curve, larger payload.",
                },
            },
            "required": ["birth_date", "birth_time"],
        },
    },
    {
        "name": "render_astrocartography_map",
        "description": (
            "Render astrocartography lines onto a static world map image "
            "(PNG or SVG) and save it to disk. Returns the file path -- "
            "this tool does not display the image itself, so tell the "
            "person where it was saved."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
                "birth_time": {"type": "string", "description": "HH:MM or HH:MM:SS, 24hr, in UT"},
                "output_path": {
                    "type": "string",
                    "description": "Optional. Where to save the image (.png or .svg). Defaults to output/astrocartography_<birth_date>.png",
                },
                "bodies": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Optional. Subset of planet names to draw (default: all 10).",
                },
                "title": {"type": "string", "description": "Optional. Map title text."},
            },
            "required": ["birth_date", "birth_time"],
        },
    },
    {
        "name": "render_interactive_astrocartography_map",
        "description": (
            "Render astrocartography lines as a single self-contained "
            "interactive HTML file -- pan/zoom, a layer-control panel to "
            "show/hide individual planets, and hover tooltips naming each "
            "line. Opens directly in a browser (file://, no server, no "
            "internet needed to view). Prefer this over "
            "render_astrocartography_map when the person wants to explore "
            "the map rather than just see a fixed snapshot. Returns the "
            "file path -- tell the person to open it in a browser."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
                "birth_time": {"type": "string", "description": "HH:MM or HH:MM:SS, 24hr, in UT"},
                "output_path": {
                    "type": "string",
                    "description": "Optional. Where to save the .html file. Defaults to output/astrocartography_<birth_date>.html",
                },
                "bodies": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Optional. Subset of planet names to draw (default: all 10).",
                },
                "title": {"type": "string", "description": "Optional. Map title text."},
            },
            "required": ["birth_date", "birth_time"],
        },
    },
]

_ALL_WEIGHTS: Dict[str, int] = {n: d["weight"] for n, d in PLANET_CATALOG.items()}
_ALL_WEIGHTS.update(COMPUTED_WEIGHTS)


def birth_card_str(greg_date: _date) -> Optional[str]:
    """Earth (birth) card for a date, in cardology's compact notation
    ('QH', '10C', ...). Ports wealth_algorithm.py's own birth_card_str()
    exactly, using this project's date_to_cosmic_day() instead of a
    standalone cosmic_calendar import. Returns None on the cosmic Leap/
    Joker Day (Dec 18) -- that day sits outside the 52-card Master
    Spreads, so no cardology profile exists for it, matching the source."""
    info = date_to_cosmic_day(greg_date.isoformat())
    if "error" in info or info.get("card") is None:
        return None
    suit_symbol, rank = info["card"]
    suit = _SUIT_SYMBOL_TO_LETTER.get(suit_symbol)
    if suit is None:  # the Joker
        return None
    return f"{rank}{suit}"


def handle_get_cosmic_cards(date_str: str) -> Dict[str, Any]:
    """Full Cosmic Card + Tarot reading for a date. NOT scored -- see
    module docstring. Returns a clear note (not an error) on the cosmic
    Leap/Joker Day, matching wealth_algorithm.py's own graceful skip."""
    try:
        d = _date.fromisoformat(date_str)
    except ValueError as exc:
        return {"error": f"Date parse error: {exc}"}

    earth = birth_card_str(d)
    if earth is None:
        return {
            "date": date_str,
            "cosmic_cards": None,
            "note": ("This date falls on the cosmic Leap Day (the Joker) -- "
                     "no Master Spread position exists, so there's no cosmic "
                     "card profile for it."),
        }

    cosmic_profile = cardology.derive_cosmic_cards(earth)
    tarot_profile = tarot.derive_tarot_profile(cosmic_profile)

    cards = {}
    for field in cosmic_profile.__dataclass_fields__:
        c = getattr(cosmic_profile, field)
        t = getattr(tarot_profile, field)
        cards[field] = {
            "card": c.symbol,
            "card_name": c.full_name,
            "tarot_name": t.name,
            "tarot_number": t.number,
            "cosmic_number": tarot.cosmic_card_number(c),
        }

    return {
        "date": date_str,
        "earth_card": earth,
        "cards": cards,
        "note": "Descriptive only -- not folded into the wealth score, per the source design.",
    }


class SessionState:
    """Holds charts computed during this conversation, keyed by label.
    Lives only in memory -- separate from ChartCache, which persists raw
    ephemeris results to disk across process runs."""

    def __init__(self):
        self.charts: Dict[str, dict] = {}

    def store(self, label: str, chart_dict: dict) -> None:
        self.charts[label] = chart_dict

    def get(self, label: str) -> Optional[dict]:
        return self.charts.get(label)


def _rebuild_natal_chart(chart_dict: dict) -> NatalChart:
    """Reconstruct a scoring-ready NatalChart from a serialized chart_dict
    (chart_to_dict() output, as stored in SessionState/ChartCache).
    Weights aren't part of the serialized form (they're static catalog
    data, not per-chart) so they're rebuilt from PLANET_CATALOG/
    COMPUTED_WEIGHTS directly rather than round-tripped."""
    positions = {name: info["lon"] for name, info in chart_dict["bodies"].items()}
    nc = NatalChart(
        birth_date=chart_dict["birth_date"], birth_time=chart_dict["birth_time"],
        latitude=chart_dict["latitude"], longitude=chart_dict["longitude"],
        julian_day=0.0,  # not needed downstream; scoring reads positions/body_info only
        sidereal=chart_dict["sidereal"],
        ascendant=chart_dict["ascendant"], is_day=chart_dict["is_day_chart"],
        enneagram_type=chart_dict.get("enneagram_type"), enneagram_wing=chart_dict.get("enneagram_wing"),
        mbti_type=chart_dict.get("mbti_type"), mbti_variant=chart_dict.get("mbti_variant"),
        numerology_name=chart_dict.get("numerology_name"),
        positions=positions, weights=dict(_ALL_WEIGHTS),
        body_info=chart_dict["bodies"],
        star_positions=chart_dict["fixed_stars"],
        dignity_only_bodies=chart_dict.get("dignity_only_bodies", {}),
        errors=list(chart_dict.get("errors", [])),
    )
    return nc


class WealthAgent:
    def __init__(self, api_key: Optional[str] = None, cache: Optional[ChartCache] = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.session = SessionState()
        self.cache = cache or ChartCache()
        self.history: list[Dict[str, Any]] = []

    # -- tool dispatch --------------------------------------------------------
    def _dispatch(self, tool_name: str, tool_input: dict) -> dict:
        """Every branch returns a plain dict; every failure is caught and
        turned into {"error": ...} rather than raised, so a broken tool
        call surfaces to the model as data it can explain, not a crash."""
        try:
            if tool_name == "get_natal_chart":
                bd, bt = tool_input["birth_date"], tool_input["birth_time"]
                lat, lon = tool_input["latitude"], tool_input["longitude"]
                label = tool_input["label"]
                numerology_name = tool_input.get("numerology_name")

                try:
                    enneagram_core, enneagram_wing = (
                        parse_enneagram_input(tool_input["enneagram_type"])
                        if tool_input.get("enneagram_type") is not None else (None, None)
                    )
                    mbti_code, mbti_variant = (
                        parse_mbti_input(tool_input["mbti_type"])
                        if tool_input.get("mbti_type") is not None else (None, None)
                    )
                except ValueError as exc:
                    return {"error": str(exc)}

                cached = self.cache.get(bd, bt, lat, lon)
                if cached is not None:
                    chart_dict = dict(cached)
                else:
                    chart = get_natal_chart(bd, bt, lat, lon, sidereal=True)  # always sidereal
                    chart_dict = chart_to_dict(chart)
                    # Cache only the astronomical portion. enneagram_type/
                    # mbti_type/numerology_name are per-PERSON metadata,
                    # not tied to (date,time,lat,lon) -- baking them into
                    # the disk cache could leak one person's stated data
                    # onto a different chart that happens to share birth data.
                    cacheable = dict(chart_dict)
                    cacheable.pop("enneagram_type", None)
                    cacheable.pop("enneagram_wing", None)
                    cacheable.pop("mbti_type", None)
                    cacheable.pop("mbti_variant", None)
                    cacheable.pop("numerology_name", None)
                    self.cache.set(bd, bt, lat, lon, cacheable)

                chart_dict["enneagram_type"] = enneagram_core
                chart_dict["enneagram_wing"] = enneagram_wing
                chart_dict["mbti_type"] = mbti_code
                chart_dict["mbti_variant"] = mbti_variant
                chart_dict["numerology_name"] = numerology_name

                self.session.store(label, chart_dict)
                return chart_dict

            elif tool_name == "score_wealth":
                label = tool_input["label"]
                chart_dict = self.session.get(label)
                if chart_dict is None:
                    return {"error": f"No chart stored under label '{label}'. "
                                      f"Call get_natal_chart first."}
                nc = _rebuild_natal_chart(chart_dict)

                # Compute aspects/dignities directly (not via score_wealth()'s
                # convenience wrapper) because numerology needs those logs
                # BEFORE the raw score is finalized -- it scales each cipher's
                # ruling planet's already-computed contribution, exactly like
                # your source's main() computes asp_score/dig_bonus first,
                # then num_boost from them, then sums all three into raw.
                asp_total, asp_log = score_aspects(nc.positions, nc.weights, nc.star_positions)
                dig_total, dig_log = score_dignities(
                    nc.positions, nc.weights, nc.body_info, nc.dignity_only_bodies
                )

                numerology_boost = 0.0
                numerology_note = None
                numerology_log = None
                if nc.numerology_name:
                    if not ciphers_js_available():
                        numerology_note = (
                            f"Numerology requested (name='{nc.numerology_name}') but "
                            f"ciphers.js isn't available at {DEFAULT_CIPHERS_JS_PATH} -- "
                            f"skipped, not estimated. Upload the real cipher file to enable this tier."
                        )
                    else:
                        try:
                            y, m, d = (int(p) for p in nc.birth_date.split("-"))
                            profile = compute_numerology_profile(nc.numerology_name, (y, m, d))
                            numerology_boost, numerology_log = score_numerology_boost(
                                profile, asp_log, dig_log
                            )
                        except Exception as exc:
                            numerology_note = f"Numerology failed: {exc} -- skipped."
                            numerology_boost = 0.0

                wealth_result = finalize_wealth_score(
                    asp_total, dig_total, asp_log, dig_log, nc.is_day, numerology_boost
                )
                result_dict = score_result_to_dict(wealth_result, max_aspect_log=25)
                if numerology_log:
                    result_dict["numerology_log"] = numerology_log
                    result_dict["boosts_applied"].append(
                        f"numerology boost ({nc.numerology_name}, "
                        f"{numerology_boost:+.2f} added to raw score before normalization)"
                    )
                if numerology_note:
                    result_dict["numerology_note"] = numerology_note

                birth_greg_date = _date.fromisoformat(chart_dict["birth_date"])
                as_of = tool_input.get("as_of_date")
                as_of_date = _date.fromisoformat(as_of) if as_of else None
                result_dict = apply_all_cosmic_boosts(
                    result_dict, nc.positions, birth_greg_date, as_of_date=as_of_date
                )

                if nc.enneagram_type is not None or nc.mbti_type is not None:
                    bodies_involved = set()
                    for e in result_dict.get("aspect_log", []):
                        bodies_involved.update(p.strip() for p in e["pair"].split(" / "))
                    for e in result_dict.get("dignity_log", []):
                        bodies_involved.add(e["planet"])
                    body_constellations = bodies_to_archetype_wheel(nc.positions)
                    result_dict = apply_typology_boost(
                        result_dict, nc.enneagram_type, nc.mbti_type,
                        bodies_involved, body_constellations,
                    )

                return result_dict

            elif tool_name == "cosmic_day_to_date":
                return cosmic_day_to_date(
                    tool_input["cosmic_year"], tool_input["month"], tool_input["day_in_month"]
                )

            elif tool_name == "date_to_cosmic_day":
                return date_to_cosmic_day(tool_input["gregorian_date"])

            elif tool_name == "recall_chart":
                label = tool_input["label"]
                chart_dict = self.session.get(label)
                if chart_dict is None:
                    return {"error": f"No chart stored under label '{label}'"}
                return chart_dict

            elif tool_name == "list_recalled_charts":
                return {"labels": list(self.session.charts.keys())}

            elif tool_name == "get_gate_for_longitude":
                return handle_get_gate_for_longitude(tool_input["sidereal_longitude"])

            elif tool_name == "get_chart_gates":
                return handle_get_chart_gates(
                    birth_date=tool_input["birth_date"],
                    latitude=tool_input["latitude"],
                    longitude=tool_input["longitude"],
                    birth_time=tool_input.get("birth_time", "12:00:00"),
                    name=tool_input.get("name", "Native"),
                )

            elif tool_name == "get_day_gate":
                return handle_get_day_gate(tool_input.get("date", ""))

            elif tool_name == "get_typology_info":
                ent = tool_input.get("enneagram_type")
                mbti = tool_input.get("mbti_type")
                out: Dict[str, Any] = {}
                if ent is not None:
                    if ent in ENNEAGRAM_CORE:
                        out["enneagram"] = {"type": ent, **ENNEAGRAM_CORE[ent]}
                    else:
                        out["enneagram_error"] = f"{ent} isn't a valid Enneagram type (1-9)"
                if mbti is not None:
                    code = mbti.strip().upper()
                    if code in VALID_MBTI_CODES:
                        out["mbti"] = {
                            "code": code,
                            "constellations": [
                                {"constellation": c, "archetype": a, "ruler": MBTI_BY_CONSTELLATION[c]["ruler"]}
                                for c, a in MBTI_CONSTELLATIONS[code]
                            ],
                        }
                    else:
                        out["mbti_error"] = f"'{mbti}' isn't a real 4-letter MBTI code"
                if not out:
                    out["error"] = "Provide enneagram_type and/or mbti_type"
                return out

            elif tool_name == "get_mayan_sign":
                try:
                    d = _date.fromisoformat(tool_input["date"])
                except ValueError as exc:
                    return {"error": f"Date parse error: {exc}"}
                return date_to_tzolkin(d)

            elif tool_name == "get_mayan_tree_of_life":
                try:
                    d = _date.fromisoformat(tool_input["date"])
                except ValueError as exc:
                    return {"error": f"Date parse error: {exc}"}
                return tree_of_life(d)

            elif tool_name == "get_numerology_profile":
                if not ciphers_js_available():
                    return {"error": (
                        f"ciphers.js isn't available at {DEFAULT_CIPHERS_JS_PATH}. "
                        f"The numerology engine is ready but has no cipher data to "
                        f"work with -- this isn't estimable without the real file."
                    )}
                try:
                    y, m, d = (int(p) for p in tool_input["birth_date"].split("-"))
                    profile = compute_numerology_profile(tool_input["name"], (y, m, d))
                    return numerology_profile_to_dict(profile)
                except Exception as exc:
                    return {"error": f"{type(exc).__name__}: {exc}"}

            elif tool_name == "get_core_numerology_profile":
                if not ciphers_js_available():
                    return {"error": (
                        f"ciphers.js isn't available at {DEFAULT_CIPHERS_JS_PATH}. "
                        f"Expression/Soul Urge/Personality read the standard "
                        f"Pythagorean letter table from a cipher literally named "
                        f"'Pythagorean' in that file -- can't compute without it."
                    )}
                try:
                    by, bm, bd_ = (int(p) for p in tool_input["birth_date"].split("-"))
                    target = tool_input.get("target_date")
                    ty, tm, td = (int(p) for p in target.split("-")) if target else (by, bm, bd_)
                    profile = compute_core_numerology_profile(
                        first_name=tool_input["first_name"],
                        last_name=tool_input["last_name"],
                        middle_names=tool_input.get("middle_names"),
                        suffix=tool_input.get("suffix"),
                        birth_date=(by, bm, bd_),
                        target_date=(ty, tm, td),
                    )
                    return core_numerology_profile_to_dict(profile)
                except Exception as exc:
                    return {"error": f"{type(exc).__name__}: {exc}"}

            elif tool_name == "get_cosmic_cards":
                return handle_get_cosmic_cards(tool_input["date"])

            elif tool_name == "get_astrocartography_lines":
                bodies = tool_input.get("bodies")
                if bodies:
                    invalid = [b for b in bodies if b not in ACG_BODIES]
                    if invalid:
                        return {"error": f"Unknown bodies: {invalid}. Valid: {sorted(ACG_BODIES)}"}
                lat_step = tool_input.get("lat_step", DEFAULT_LAT_STEP)
                lines = compute_lines(
                    tool_input["birth_date"], tool_input["birth_time"],
                    lat_step=lat_step, bodies=bodies,
                )
                return {
                    "birth_date": tool_input["birth_date"],
                    "birth_time": tool_input["birth_time"],
                    "lines": {name: body_lines_to_dict(bl) for name, bl in lines.items()},
                    "note": "Not scored -- descriptive only. Independent of sidereal/tropical.",
                }

            elif tool_name == "render_astrocartography_map":
                bodies = tool_input.get("bodies")
                if bodies:
                    invalid = [b for b in bodies if b not in ACG_BODIES]
                    if invalid:
                        return {"error": f"Unknown bodies: {invalid}. Valid: {sorted(ACG_BODIES)}"}
                bd = tool_input["birth_date"]
                lines = compute_lines(bd, tool_input["birth_time"], bodies=bodies)
                output_path = tool_input.get("output_path") or f"output/astrocartography_{bd}.png"
                path = render_map(
                    lines, output_path,
                    title=tool_input.get("title"), bodies=bodies,
                )
                return {
                    "path": path,
                    "bodies_drawn": bodies if bodies else list(lines.keys()),
                    "note": "Static image -- open it directly to view. Not scored.",
                }

            elif tool_name == "render_interactive_astrocartography_map":
                bodies = tool_input.get("bodies")
                if bodies:
                    invalid = [b for b in bodies if b not in ACG_BODIES]
                    if invalid:
                        return {"error": f"Unknown bodies: {invalid}. Valid: {sorted(ACG_BODIES)}"}
                bd = tool_input["birth_date"]
                lines = compute_lines(bd, tool_input["birth_time"], bodies=bodies)
                output_path = tool_input.get("output_path") or f"output/astrocartography_{bd}.html"
                path = render_interactive_map(
                    lines, output_path,
                    title=tool_input.get("title"), bodies=bodies,
                )
                return {
                    "path": path,
                    "bodies_drawn": bodies if bodies else list(lines.keys()),
                    "note": ("Self-contained interactive HTML -- open in any browser, no "
                             "internet needed. Not scored."),
                }

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    # -- main loop --------------------------------------------------------------
    def send(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history,
            )

            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return "".join(
                    block.text for block in response.content if block.type == "text"
                )

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._dispatch(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            self.history.append({"role": "user", "content": tool_results})

        return ("[Stopped after reaching the tool-call safety limit -- the "
                "agent may be stuck in a loop. Check the conversation above.]")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Set ANTHROPIC_API_KEY before running, e.g.:\n"
            "  $env:ANTHROPIC_API_KEY = 'your-key-here'   (current PowerShell session)\n"
            "  setx ANTHROPIC_API_KEY 'your-key-here'      (persists for new sessions)"
        )

    agent = WealthAgent()
    print("Wealth Agent -- true sidereal / Capricorn Prometheus framework.")
    print("Ctrl+C to exit.\n")
    while True:
        try:
            user_input = input("you> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
        if not user_input:
            continue
        reply = agent.send(user_input)
        print(f"\nagent> {reply}\n")
