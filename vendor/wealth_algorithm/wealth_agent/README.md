# Wealth Algorithm Agent

This update reconciles `wealth_agent/` against the standalone files from
the separate "64-Gate Human Design system with I Ching and elements"
session -- and in the process of that reconciliation, catches and fixes
a real bug in fixed-star positions that's been affecting every wealth
score since fixed stars were first added.

## What the reconciliation found

The 5 uploaded files (`calendar_bridge.py`, `human_design_gates.py`,
`gate_calendar_bridge.py`, `gates.py`, `README.md`) turned out to be from
that other session's own standalone build -- which explains the
`ModuleNotFoundError` from last message exactly: that session had no
visibility into this project's `tools/` package structure, so it wrote
flat, absolute imports (`import calendar_bridge as cb`) that assume every
file sits in one directory. That's incompatible with how this project is
actually organized, so those files were used as a reference to verify
against, not copied in wholesale (which would have reintroduced the same
import error).

The verification was direct, not a read-through: `calendar_bridge.py`
diffed byte-identical to what's already here. `human_design_gates.py`'s
core data (`GATE_ELEMENTS`, the wheel sequence, the anchor point) matched
exactly, confirmed by sweeping all 64 gate boundaries through both
versions. For `gates.py` and `gate_calendar_bridge.py`, their *actual,
unmodified* code was run -- with `wealth_algorithm_updated_house_system.py`
standing in for the `wealth_algorithm` module they import -- against this
project's package-integrated equivalents, for the same real chart. Every
field matched: Sun's Gate/Line/House, sidereal longitude, the day-gate
computation, all of it.

## The bug the verification actually caught

The other session's own README explicitly flagged one thing as unfixed:
`calc_stars()` hardcoding tropical flags for every star regardless of the
chart's sign mode. That flag was real -- and still present, unfixed,
in this project's `tools/chart.py` too. Checked directly rather than
assumed: computed Regulus both ways for a real chart and found a ~24.66
degree gap, the size of the ayanamsa at that date, exactly what the bug
predicts.

**Why this matters more than a display glitch**: `calc_stars()`'s output
feeds `score_aspects()` directly. Every wealth score this project has
ever computed that involved a planet-star aspect was checking angular
separation between a sidereal-corrected planet and a tropical (mislabeled
sidereal) star -- two different reference frames, a full ayanamsa apart.
Fixed by mirroring `calc_planets()`'s own sidereal convention exactly
(`FLG_SIDEREAL` + `SIDM_LAHIRI`) rather than a manual post-hoc
subtraction, and checked that the two methods agree to within ~15
arcseconds using the correct call order -- an earlier version of that
specific check used the wrong order (reading the ayanamsa before setting
the sidereal mode) and showed a misleading 0.88 degree gap that turned
out to be comparing against the wrong ayanamsa mode entirely, not a real
discrepancy. Worth knowing since it means the fix was checked twice, not
once: first against the wrong comparison, then corrected and re-checked
before being trusted.

**Real-world effect**: the test chart's `raw_score` changes with this fix
(any chart with star-involving aspects will), since the aspect log is now
checking genuinely different, correct angular relationships -- not a
rounding change, a real correction.

## Everything else: confirmed already consistent

Star catalog naming quirks (Galactic Center resolves directly; Solar
Apex and Super Galactic Center are cataloged as "Apex" and "Messier 87"
respectively) -- already handled correctly. The house system, the Gate
34 Selenium/Xenon correction, the gate-boundary floating-point rounding
guard -- all already present and verified byte-for-byte against the
guidance files' own data. Nothing needed to change for any of these; the
reconciliation confirmed they were already right rather than finding
more to fix.

## Structure

Unchanged from the last delivered version except:

```text
wealth_agent/
  tools/
    chart.py    # calc_stars() now takes a sidereal parameter and uses it correctly
```
