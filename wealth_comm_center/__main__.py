"""Source-tree CLI sharing the exact web/MCP calculation service."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="wealth_command_center")
    parser.add_argument("operation", choices=["report", "map", "sky", "card"])
    parser.add_argument("--profile", type=Path, required=True, help="A JSON profile you are authorized to use")
    parser.add_argument("--date", help="Explicit reference date, YYYY-MM-DD")
    parser.add_argument("--body", default="sun", help="Card body ID")
    parser.add_argument("--locale", choices=["en", "ja", "zh-CN", "th", "ko", "vi"], default="en")
    parser.add_argument("--svg", action="store_true", help="Output SVG for the card operation")
    args = parser.parse_args()
    from .engine import build_map, build_report, build_sky_state
    try:
        with args.profile.open(encoding="utf-8") as stream:
            profile = json.load(stream)
        if args.operation == "map":
            result = build_map(profile)
        elif args.operation == "sky":
            result = build_sky_state(profile)
        else:
            result = build_report(profile, args.date)
            if args.operation == "card":
                from .cosmic_cards import resolve_card, render_svg
                result = resolve_card(result, args.body, args.locale)
                if args.svg:
                    result = render_svg(result)
        sys.stdout.reconfigure(encoding="utf-8")
        print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Unable to produce output: {exc}\n")


if __name__ == "__main__":
    main()
