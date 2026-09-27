"""Exercise the actual optional stdio transport with synthetic, unsaved inputs."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from wealth_command_center.mcp_server import calculate_profile


def test_mcp_rejects_unsupported_tropical_contract():
    with pytest.raises(ValueError, match="sidereal"):
        calculate_profile("1990-01-15", "12:00", "Asia/Tokyo", 35.68, 139.76, "2026-09-26", False)


def test_optional_mcp_real_stdio_initialize_list_and_call():
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "wealth_command_center.mcp_server"],
            cwd=Path(__file__).resolve().parents[1],
            env={"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        )
        async with asyncio.timeout(30):
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "Wealth Command Center"
                    listed = await session.list_tools()
                    assert [tool.name for tool in listed.tools] == ["calculate_profile"]
                    assert listed.tools[0].annotations.readOnlyHint is True
                    assert listed.tools[0].annotations.destructiveHint is False
                    assert "report_date" in listed.tools[0].inputSchema["required"]
                    resources = await session.read_resource("wealth://capabilities")
                    capabilities = json.loads(resources.contents[0].text)
                    assert "no stored data access" in capabilities["scope"]
                    result = await session.call_tool("calculate_profile", {
                        "birth_date": "1990-01-15", "birth_time": "12:00",
                        "timezone": "Asia/Tokyo", "latitude": 35.68, "longitude": 139.76,
                        "report_date": "2026-09-26",
                    })
                    assert result.isError is False
                    report = result.structuredContent
                    assert report["schema_version"] == "1.0"
                    assert report["profile_id"] is None
                    assert report["birth_utc"] == "1990-01-15T03:00:00Z"
                    assert 0 <= report["score"]["value"] <= 100
                    assert report["provenance"]["network_downloads"] is False
                    assert any(item["id"] == "score.symbolic" for item in report["evidence"])
                    rejected = await session.call_tool("calculate_profile", {
                        "birth_date": "1990-01-15", "birth_time": "12:00",
                        "timezone": "Asia/Tokyo", "latitude": 35.68, "longitude": 139.76,
                        "report_date": "2026-09-26", "sidereal": False,
                    })
                    assert rejected.isError is True
                    assert "sidereal" in rejected.content[0].text

    asyncio.run(exercise())
