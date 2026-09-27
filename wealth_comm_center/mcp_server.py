"""Optional local stdio MCP adapter; no access to web users or their database."""

from __future__ import annotations

import json

from .agent import tool_manifest


def calculate_profile(
    birth_date: str, birth_time: str, timezone: str, latitude: float, longitude: float,
    report_date: str, sidereal: bool = True,
) -> dict[str, object]:
    """Calculate explicit input only. Nothing is saved or looked up by user/profile ID.

    All dates are ISO dates and the local birth time is HH:MM[:SS]. Timezone is an
    IANA identifier. report_date is mandatory so this tool has no hidden today.
    The framework is sidereal only; sidereal=False is explicitly rejected.
    Only provide personal birth data when its owner consents to the MCP host.
    """
    from .engine import build_report

    if sidereal is not True:
        raise ValueError("Only the upstream custom sidereal framework is supported; sidereal must be true.")
    return build_report({
        "birth_date": birth_date, "birth_time": birth_time, "timezone": timezone,
        "latitude": latitude, "longitude": longitude, "sidereal": sidereal,
    }, date=report_date)


def create_server():
    try:
        # The optional dependency is deliberately pinned to the maintained v1 line.
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError("Install the optional MCP extra: pip install -e '.[mcp]'") from exc
    server = FastMCP("Wealth Command Center", instructions=(
        "Use explicit caller-provided inputs only. This server has no accounts, stored profiles, "
        "desktop control, or financial execution tools. Symbolic scores do not predict wealth."
    ))
    server.tool(
        name="calculate_profile",
        structured_output=True,
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                    idempotentHint=True, openWorldHint=False),
    )(calculate_profile)

    @server.resource("wealth://capabilities")
    def capabilities() -> str:
        return json.dumps({
            "scope": "local explicit-input calculations; no stored data access",
            "tools": [{"name": "calculate_profile", "deterministic": True, "mutates": False,
                       "requires": ["birth_date", "birth_time", "timezone", "latitude", "longitude", "report_date"]}],
            "web_agent_tools": tool_manifest(),
        })

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
