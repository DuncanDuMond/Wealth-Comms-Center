# 64-Gate Human Design System

Layers the Human Design I Ching gate wheel onto the sidereal ecliptic,
keys each of the 64 gates to the chemical element sharing its atomic
number, and bridges it into the Cosmic Calendar and wealth-scoring system.

## Files

| File | Status | Purpose |
| --- | --- | --- |
| `human_design_gates.py` | New | Core 64-gate wheel: data, lookup engine, CLI |
| `calendar_bridge.py` | **Extended** (yours, uploaded) | Added `BOOST_DAY_GATE` + optional gate params on `apply_cosmic_boosts()` |
| `gate_calendar_bridge.py` | New | Computes the Day Gate; orchestrates all three boost tiers in one call |
| `gates.py` | New | `wealth_agent/tools/` wrapper — 3 agent-callable tools |

All four live in the same directory as `wealth_algorithm.py` and
`cosmic_calendar.py` (or wherever those two are importable from).

---

## 1. The wheel (`human_design_gates.py`)

- **Anchor**: Gate 41 begins at 2°23'23" ("Aquarius") = 296.843500° sidereal, exactly as given.
- **Width**: 360° ÷ 64 = 5.625° per gate, fixed.
- **Sequence**: the canonical Human Design mandala order (41→19→13→49→...), not numeric order.
- **Gate ↔ Element**: every gate N is keyed to the element with atomic number Z=N — Gate 1 is Hydrogen, Gate 64 is Gadolinium, all 64 checked against the real periodic table at import time (`_validate()`).
- **Bonus Line**: each gate also reports a Line 1-6 (5.625°/6 = 0.9375° each) — free from the same math, included since Human Design always has it, but Gate-level was the actual ask.

**Data correction**: the original list had "34 – Xenon" twice (Gate 34 is Selenium). Xenon's real atomic number is 54, and Gate 54 was the only number 1-64 missing — so Gate 54 is Xenon, 歸妹 (guī mèi). Gate 41's own hexagram (not given, only its degree was) is filled in as 損 (sǔn), I Ching 41.

**Bug caught during testing**: a longitude landing within floating-point noise of an exact gate boundary (e.g. a full 360° past the anchor) could floor into the wrong gate. Fixed with a rounding guard (`_wrap_deg`); swept all 64 boundaries + wraparounds to confirm.

**Independent of `_13SIGN_TROP`**: this wheel's "Aquarius" anchor is a separate reference point from the IAU-constellation-boundary Aquarius already in `wealth_algorithm.py` (they differ by ~8.6° at the current ayanamsa). They're independent overlays on the same 360° sidereal ring — like two clock hands on one face — not meant to share an edge. `bodies_to_gates()` reports both side by side (Gate + `_13SIGN_TROP` constellation) without reconciling them.

```bash
python human_design_gates.py                          # static 64-gate wheel table
python human_design_gates.py --sid-lon 118.2           # single longitude lookup
python human_design_gates.py --date 1990-06-15 --time 14:30:00 \
    --lat 40.71 --lon -74.01 --name Alice --output alice_gates.json
```

Key functions: `gate_for_longitude(sid_lon)`, `bodies_to_gates(lons)` — the second takes exactly what `wealth_algorithm.calc_planets()` / `all_body_positions()` return, no glue code needed.

---

## 2. Calendar boost bridge (`calendar_bridge.py` + `gate_calendar_bridge.py`)

Your `calendar_bridge.py` already had two boost tiers in `apply_cosmic_boosts()`:

| Tier | Constant | Fires when |
| --- | --- | --- |
| Month ruler | `BOOST_MONTH_RULER = 1.15` | The cosmic month's ruling planet is active in the chart's aspect/dignity log |
| Suit element | `BOOST_SUIT_ELEMENT = 1.10` | Any planet in the day-card's suit-element group is active |

Added a third, **opt-in and fully backward-compatible**:

| Tier | Constant | Fires when |
| --- | --- | --- |
| Day Gate | `BOOST_DAY_GATE = 1.15` | A body active in the chart shares its Gate with the Sun's transiting Gate that day |

**Day Gate** = the Gate the Sun sidereally occupies on a civil date — the same machinery Human Design already uses for a person's own Sun gate, just pointed at a calendar date instead of a birth date.

`apply_cosmic_boosts(score_dict, cosmic_info, gate_info=None, day_gate=None)` — the two new params default to `None`, so every existing call site behaves identically to before unless it opts in. No new imports were added to `calendar_bridge.py` itself; it stays free of any astrology-module dependency, same as before — the caller supplies already-computed data, same pattern as `score_dict`/`cosmic_info` already use.

`gate_calendar_bridge.py` does the orchestration:

```python
import gate_calendar_bridge as gcb

# One call: computes cosmic_info, this chart's gate_info, and today's
# Sun-Gate, then applies all three tiers.
result = gcb.apply_all_cosmic_boosts(score_dict, lons, greg_date)
```

Or piecemeal:

```python
gcb.day_gate(date(2026, 12, 25))          # -> Gate/Line/element/hexagram + card, for one date
gcb.gate_boost_weights(gate_info, date)   # -> {body: 1.15 or 1.0}, lighter-weight, no score_dict needed
```

**Verified against real output** (not mocks) — built an actual `score_dict` from a test chart via your real `score_aspects`/`score_dignities`/`normalize`:

- Old-style calls (no gate args) → byte-identical to pre-change behavior.
- On a date where the chart's own Sun/Selena match the transiting Day Gate, all three tiers fire correctly together.
- Forced a guaranteed non-match → confirmed zero false positives.

**`COSMIC_MONTH_RULERS` check**: verified by directly computing the Sun's real sidereal sign at each cosmic month's Gregorian midpoint. The existing table is correct — Leo (38.9° wide) legitimately spans two consecutive month-midpoints, and both Cancer (15.7° wide) and Scorpio (5.3° wide, one of the narrowest in the real IAU boundaries) are legitimately never hit by any midpoint sample, 27.6° apart as the Sun moves. Left unchanged.

---

## 3. Agent tool (`gates.py` → `wealth_agent/tools/gates.py`)

Three Anthropic-format tools:

| Tool | Input | Returns |
| --- | --- | --- |
| `get_gate_for_longitude` | `sidereal_longitude` | One Gate/Line/element/hexagram |
| `get_chart_gates` | `date`, `latitude`, `longitude`, optional `time`/`name` | All 14 bodies' Gates + constellations |
| `get_day_gate` | optional `date` (defaults to today) | That date's Sun-Gate + calendar card |

All three tested end-to-end and confirmed JSON-serializable (a hard requirement for a `tool_result`).

**Two open assumptions**, since `agent_loop.py` / `tools/chart.py` / `cache.py` weren't available to check against:

1. **Registration shape** — `TOOLS` (list of schemas) + `HANDLERS` (name → function) is the most common pattern; if your real dispatch loop differs (class-based registry, decorator), only the registration at the bottom needs to change, not the schemas or handler bodies.
2. **Chart recomputation** — `get_chart_gates` calls `wa.all_body_positions()` independently rather than reusing a chart `tools/chart.py` may have already computed this turn. Safe, but means two ephemeris calls if both tools are invoked in the same turn. If `cache.py` memoizes by `(date, time, lat, lon)`, route through it instead.

---

## Other things worth knowing

- **`SUIT_PLANET_GROUPS`** (in `calendar_bridge.py`) is explicitly flagged in that file's own docstring as ungrounded scaffolding — a standard Tarot-suit/element convention, not derived from anything you'd shared at the time it was written. Unlike `COSMIC_MONTH_RULERS`, there's no ephemeris check that can validate or invalidate it (it's a definitional choice, not a computed fact) — worth revisiting with your own mapping if you have one, whenever convenient.
- **Ophiuchus / Month XIII** has no active ruler for the month-ruler boost: Chiron is documented in `COSMIC_MONTH_RULERS` as a label only, since Chiron isn't a tracked body in `wealth_algorithm.py`. Structurally inactive rather than fabricated — that tier just never fires for Month XIII as things stand.
- **Full agent wiring is still pending real files.** I don't have `agent_loop.py`, `tools/chart.py`, `tools/scoring.py`, `cache.py`, or `main.py` — everything above was built and tested standalone, against `wealth_algorithm.py`, `cosmic_calendar.py`, and the real `calendar_bridge.py` you uploaded. `tools/scoring.py` in particular almost certainly calls `apply_cosmic_boosts()` today and will need one small edit to pass `gate_info`/`day_gate` through — otherwise the day-gate tier just stays dormant at its default `None`, harmlessly. Upload what you can and I'll do the actual wiring against your real code instead of leaving it as tested-but-standalone.

## Dependencies

`pyswisseph`, plus `wealth_algorithm.py` and `cosmic_calendar.py` importable from the same directory. No new third-party packages introduced by any of the four files above.
