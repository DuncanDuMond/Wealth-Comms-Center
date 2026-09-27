"""
main.py — CLI entry point.

Two modes:
  python main.py --direct BIRTH_DATE BIRTH_TIME LAT LON
      Runs the chart + score pipeline directly, no Anthropic API call,
      no API key needed. Useful for validating the astrology/scoring
      logic in isolation before wiring it into the agent.

  python main.py
      Starts the interactive tool-calling agent (agent_loop.WealthAgent).
      Requires ANTHROPIC_API_KEY to be set.
"""

from __future__ import annotations

import argparse
import json
import sys

from tools.chart import get_natal_chart, chart_to_dict
from tools.scoring import (
    score_wealth, score_result_to_dict,
    score_aspects, score_dignities, finalize_wealth_score,
)
from tools.gate_calendar_bridge import apply_all_cosmic_boosts
from tools.human_design_gates import bodies_to_gates
from tools.typology import bodies_to_archetype_wheel, apply_typology_boost, parse_enneagram_input, parse_mbti_input
from tools.mayan_calendar import date_to_tzolkin, tree_of_life
from tools.astrocartography import compute_lines, body_lines_to_dict
from tools.astrocartography_map import render_map
from tools.astrocartography_interactive import render_interactive_map
from tools.numerology import (
    compute_numerology_profile, score_numerology_boost,
    ciphers_js_available, DEFAULT_CIPHERS_JS_PATH,
)
from cache import ChartCache


def run_direct(
    birth_date: str, birth_time: str, lat: float, lon: float,
    enneagram_type: str | None = None, mbti_type: str | None = None,
    numerology_name: str | None = None, render_map_path: str | None = None,
) -> None:
    # Validate/parse up front so a bad format fails before any ephemeris
    # work, with the same error message get_natal_chart's own dispatch
    # would give -- one parsing path (typology.py), not two.
    enneagram_core, enneagram_wing = parse_enneagram_input(enneagram_type) if enneagram_type else (None, None)
    mbti_code, mbti_variant = parse_mbti_input(mbti_type) if mbti_type else (None, None)

    cache = ChartCache()
    cached = cache.get(birth_date, birth_time, lat, lon)
    if cached is not None:
        chart_dict = dict(cached)
        print("(loaded from cache)", file=sys.stderr)
    else:
        chart = get_natal_chart(birth_date, birth_time, lat, lon, sidereal=True)
        chart_dict = chart_to_dict(chart)
        cacheable = dict(chart_dict)
        cacheable.pop("enneagram_type", None)
        cacheable.pop("enneagram_wing", None)
        cacheable.pop("mbti_type", None)
        cacheable.pop("mbti_variant", None)
        cacheable.pop("numerology_name", None)
        cache.set(birth_date, birth_time, lat, lon, cacheable)

    chart_dict["enneagram_type"] = enneagram_core
    chart_dict["enneagram_wing"] = enneagram_wing
    chart_dict["mbti_type"] = mbti_code
    chart_dict["mbti_variant"] = mbti_variant
    chart_dict["numerology_name"] = numerology_name

    if chart_dict["errors"]:
        print("Chart computed with warnings:", file=sys.stderr)
        for err in chart_dict["errors"]:
            print(f"  - {err}", file=sys.stderr)

    from agent_loop import _rebuild_natal_chart  # reuse the same rebuild path
    from datetime import date as _date
    nc = _rebuild_natal_chart(chart_dict)

    # Additive numerology boost, computed from aspects/dignities BEFORE
    # normalization -- see agent_loop.py's module docstring for why this
    # can't just call score_wealth() directly when numerology is involved.
    asp_total, asp_log = score_aspects(nc.positions, nc.weights, nc.star_positions)
    dig_total, dig_log = score_dignities(nc.positions, nc.weights, nc.body_info, nc.dignity_only_bodies)
    numerology_boost = 0.0
    numerology_log = None
    if numerology_name:
        if not ciphers_js_available():
            print(f"  [!] Numerology: ciphers.js not found at {DEFAULT_CIPHERS_JS_PATH} -- skipped.",
                  file=sys.stderr)
        else:
            y, m, d = (int(p) for p in birth_date.split("-"))
            profile = compute_numerology_profile(numerology_name, (y, m, d))
            numerology_boost, numerology_log = score_numerology_boost(profile, asp_log, dig_log)
    wealth_result = finalize_wealth_score(asp_total, dig_total, asp_log, dig_log, nc.is_day, numerology_boost)
    result_dict = score_result_to_dict(wealth_result)
    if numerology_log:
        result_dict["numerology_log"] = numerology_log
        result_dict["boosts_applied"].append(
            f"numerology boost ({numerology_name}, "
            f"{numerology_boost:+.2f} added to raw score before normalization)"
        )

    boosted = apply_all_cosmic_boosts(result_dict, nc.positions, _date.fromisoformat(birth_date))

    if nc.enneagram_type is not None or nc.mbti_type is not None:
        bodies_involved = set()
        for e in boosted.get("aspect_log", []):
            bodies_involved.update(p.strip() for p in e["pair"].split(" / "))
        for e in boosted.get("dignity_log", []):
            bodies_involved.add(e["planet"])
        body_constellations = bodies_to_archetype_wheel(nc.positions)
        boosted = apply_typology_boost(
            boosted, nc.enneagram_type, nc.mbti_type, bodies_involved, body_constellations
        )

    gates = bodies_to_gates(nc.positions)

    # Mayan Tzolkin is purely a function of birth_date -- no extra input
    # needed, unlike enneagram/mbti which must be given. NOT wired into
    # the score -- see agent_loop.py's module docstring for why.
    mayan = {
        "sign": date_to_tzolkin(_date.fromisoformat(birth_date)),
        "tree_of_life": tree_of_life(_date.fromisoformat(birth_date)),
    }

    # Cosmic Playing Cards + Tarot: also purely a function of birth_date,
    # also NOT wired into the score -- matches wealth_algorithm.py's own
    # design exactly (computed and reported, never scored). Reuses
    # agent_loop's handler directly so there's one implementation, not two.
    from agent_loop import handle_get_cosmic_cards
    cosmic_cards = handle_get_cosmic_cards(birth_date)

    # Astrocartography: birth date/time only, no location (location is
    # what these lines solve for). Also NOT wired into the score -- see
    # agent_loop.py's module docstring. No source script exists for this
    # feature; verified instead against an independent solver (pyswisseph's
    # own rise_trans) -- see tools/astrocartography.py's module docstring.
    acg_lines = compute_lines(birth_date, birth_time)
    astrocartography = {name: body_lines_to_dict(bl) for name, bl in acg_lines.items()}

    map_path = None
    if render_map_path:
        # .html -> interactive (pan/zoom, toggle planets, tooltips);
        # anything else (.png/.svg) -> static image. One flag, extension
        # picks the renderer, rather than a second flag to choose between them.
        if render_map_path.lower().endswith(".html"):
            map_path = render_interactive_map(
                acg_lines, render_map_path,
                title=f"Astrocartography -- {birth_date} {birth_time} UT",
            )
        else:
            map_path = render_map(
                acg_lines, render_map_path,
                title=f"Astrocartography -- {birth_date} {birth_time} UT",
            )
        print(f"Map saved to {map_path}", file=sys.stderr)

    output = {"chart": chart_dict, "score": boosted, "gates": gates,
              "mayan": mayan, "cosmic_cards": cosmic_cards,
              "astrocartography": astrocartography}
    if map_path:
        output["astrocartography_map_path"] = map_path
    print(json.dumps(output, indent=2))


def prompt_for_typology() -> tuple[str | None, str | None]:
    """Interactive CLI prompt for Enneagram + MBTI type, run before the
    agent conversation starts. Validates with the exact same parsing
    functions get_natal_chart's dispatch uses, so a value accepted here
    is guaranteed valid there too -- loops on bad input rather than
    passing it through. Returns the raw validated strings, unparsed
    (get_natal_chart does its own parsing from the same raw format)."""
    print("Quick setup -- Enneagram and MBTI type (used for an optional")
    print("resonance boost against your chart; skip either with N/A).\n")

    enneagram_raw = None
    while enneagram_raw is None:
        raw = input("Enneagram type (e.g. 7w8, or 9, or N/A): ").strip()
        try:
            parse_enneagram_input(raw)
            enneagram_raw = raw
        except ValueError as exc:
            print(f"  {exc}\n")

    mbti_raw = None
    while mbti_raw is None:
        raw = input("MBTI type (e.g. INTJ-A, INTJ-T, or just INTJ, or N/A): ").strip()
        try:
            parse_mbti_input(raw)
            mbti_raw = raw
        except ValueError as exc:
            print(f"  {exc}\n")

    print()
    return enneagram_raw, mbti_raw


def main() -> None:
    parser = argparse.ArgumentParser(description="Wealth algorithm agent CLI")
    parser.add_argument("--direct", nargs=4,
                         metavar=("BIRTH_DATE", "BIRTH_TIME", "LATITUDE", "LONGITUDE"),
                         help="Run chart+score directly without the Anthropic agent, "
                              "e.g. --direct 1994-03-21 14:30:00 40.7128 -74.0060")
    parser.add_argument("--enneagram", type=str, metavar="TYPE",
                         help="Optional Enneagram type, only used with --direct. "
                              "Formats: '7w8' (core+wing), '9' (core only), or 'N/A'.")
    parser.add_argument("--mbti", type=str, metavar="CODE",
                         help="Optional MBTI type, only used with --direct. Formats: "
                              "'INTJ-A'/'INTJ-T' (code+variant), 'INTJ' (code only), or 'N/A'.")
    parser.add_argument("--numerology-name", type=str, metavar="NAME",
                         help="Optional name to run through the numerology cipher ring, "
                              "only used with --direct. Requires ciphers.js to be present "
                              "(see tools/numerology.py) -- skipped with a warning otherwise.")
    parser.add_argument("--render-map", type=str, metavar="PATH",
                         help="Optional. Save an astrocartography map to this path, only "
                              "used with --direct. .html -> interactive (pan/zoom, toggle "
                              "planets, tooltips); .png/.svg -> static image.")
    parser.add_argument("--skip-typology-prompt", action="store_true",
                         help="Skip the startup Enneagram/MBTI prompt in agent mode "
                              "(has no effect with --direct, which never prompts).")
    args = parser.parse_args()

    if args.direct:
        birth_date, birth_time, lat, lon = args.direct
        try:
            run_direct(birth_date, birth_time, float(lat), float(lon),
                       enneagram_type=args.enneagram, mbti_type=args.mbti,
                       numerology_name=args.numerology_name, render_map_path=args.render_map)
        except ValueError as exc:
            raise SystemExit(str(exc))
    else:
        from agent_loop import WealthAgent
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "Set ANTHROPIC_API_KEY before running the agent, or use "
                "--direct to test scoring without the API."
            )
        agent = WealthAgent()
        print("Wealth Agent -- true sidereal / Capricorn Prometheus framework.")

        enneagram_raw = mbti_raw = None
        if not args.skip_typology_prompt:
            enneagram_raw, mbti_raw = prompt_for_typology()

        print("Ctrl+C to exit.\n")
        if enneagram_raw or mbti_raw:
            # Fed into the conversation as a normal user turn, not a
            # separate API -- the model still decides when/whether to
            # call get_natal_chart with these, same as anything else it
            # learns mid-conversation. This just guarantees the values
            # were asked for and validated up front, in the exact format
            # get_natal_chart expects, rather than leaving it to chance
            # whether the model asks or how it interprets free-form input.
            preamble = "For reference going forward: "
            if enneagram_raw:
                preamble += f"my Enneagram type is {enneagram_raw}. "
            if mbti_raw:
                preamble += f"my MBTI type is {mbti_raw}."
            print(f"agent> {agent.send(preamble)}\n")

        while True:
            try:
                user_input = input("you> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break
            if not user_input:
                continue
            print(f"\nagent> {agent.send(user_input)}\n")


if __name__ == "__main__":
    main()
