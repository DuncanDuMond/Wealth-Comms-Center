# Upstream source and local adaptations

Source: [https://github.com/DuncanDuMond/Wealth-Algorithm](https://github.com/DuncanDuMond/Wealth-Algorithm)
Snapshot: `1a192eeb2a182f1a32a071d1dd51163936218e2a`

Original tracked files are retained. Wealth Command Center calls the modules
under `wealth_agent/tools` directly; it does not run the legacy CLI, import its
Anthropic agent loop, use its home-directory cache, or duplicate the root
astronomy/scoring implementation.

Local adaptations are limited to package markers; offline-only ephemeris setup
with actual returned backend reporting; polar-latitude ascendant recovery without
changing the custom house mapping; bounded map sampling; and relative imports in
the day-gate bridge, which now uses the same chart module as the report.

The custom sidereal sign boundaries, Sagittarius-first houses, metallic-ratio
aspects, dignity tables, calendar, typology, numerology, cardology, and Tarot
rules are preserved. These are symbolic conventions, not validated predictors
of financial returns. The upstream source itself flags the suit-element boost
and some cardology table transcription as provisional; WCC surfaces this.

The upstream snapshot contains no repository LICENSE file. Public distribution
requires resolving source/data rights and the separate licenses of Swiss
Ephemeris and its Python wrapper. This notice does not grant a license or
relicense upstream work.
