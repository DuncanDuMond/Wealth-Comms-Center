import json

import httpx
import pytest

from wealth_command_center import agent


REPORT = {
    "score": {"value": 73.25},
    "systems": {"gates": {"gate": 21}, "numerology": {"life_path": 3}},
    "evidence": [
        {"id": "score.symbolic", "label": "Symbolic score", "value": 73.25, "kind": "derived"},
        {"id": "chart.sun.longitude", "label": "Sun longitude", "value": 143.2, "kind": "computed"},
        {"id": "calendar.today", "label": "Today", "value": {"day": 1}, "kind": "symbolic"},
    ],
    "profile": {"name": "DO-NOT-SEND", "email": "private@example.test"},
}


@pytest.mark.parametrize("locale", ["en", "ja", "zh-CN", "th", "ko", "vi"])
def test_localized_guide_is_grounded_and_never_mutates(locale, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    before = json.dumps(REPORT)
    result = agent.respond("help", locale, REPORT)
    assert result["mode"] == "local_guide"
    assert "73.25" in result["answer"]
    assert "[score.symbolic]" in result["answer"]
    assert {e["id"] for e in result["evidence"]} <= {e["id"] for e in REPORT["evidence"]}
    assert json.dumps(REPORT) == before
    assert all(not entry["mutates"] for entry in result["tool_trace"])
    if locale != "en":
        assert result["answer"] != agent.respond("help", "en", REPORT)["answer"]


def test_no_report_does_not_invent_score():
    result = agent.respond("Tell me my score", "en", {})
    assert result["evidence"] == []
    assert "profile" in result["answer"].lower()
    assert "73" not in result["answer"]


def test_map_response_does_not_promise_rich_locations():
    result = agent.respond("Where should I relocate on the map?", "en", REPORT)
    assert "housing" in result["answer"]
    assert "does not predict" in result["answer"]


def test_cloud_not_called_without_explicit_consent(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    def fail(**kwargs):
        raise AssertionError("Must not create a cloud client")
    monkeypatch.setattr(agent.httpx, "Client", fail)
    assert agent.respond("help", "en", REPORT)["mode"] == "local_guide"


def test_missing_provider_key_is_transparent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = agent.respond("help", "en", REPORT, allow_cloud=True)
    assert result["mode"] == "local_guide"
    assert result["warnings"]


def test_unknown_evidence_from_cloud_falls_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    def handler(request):
        return httpx.Response(200, json={"content": [{
            "type": "tool_use", "id": "a", "name": "submit_answer",
            "input": {"answer": "Invented claim [not.real]", "evidence_ids": ["not.real"]},
        }]})
    original = httpx.Client
    monkeypatch.setattr(agent.httpx, "Client", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handler)
    ))
    result = agent.respond("help", "en", REPORT, allow_cloud=True)
    assert result["mode"] == "local_guide"
    assert "Invented" not in result["answer"]
    assert result["warnings"]


def test_provider_reads_evidence_but_not_profile_or_arbitrary_tools(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert "DO-NOT-SEND" not in request.content.decode()
        assert "private@example.test" not in request.content.decode()
        if len(calls) == 1:
            tool = {"type": "tool_use", "id": "read", "name": "read_evidence",
                    "input": {"evidence_ids": ["score.symbolic"]}}
        else:
            tool = {"type": "tool_use", "id": "finish", "name": "submit_answer",
                    "input": {"answer": "Treat the symbolic result as reflection [score.symbolic].",
                              "evidence_ids": ["score.symbolic"]}}
        return httpx.Response(200, json={"content": [tool]})
    original = httpx.Client
    monkeypatch.setattr(agent.httpx, "Client", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handler)
    ))
    result = agent.respond("explain", "en", REPORT, allow_cloud=True)
    assert result["mode"] == "anthropic"
    assert len(calls) == 2
    assert result["evidence"] == [REPORT["evidence"][0]]
    assert result["tool_trace"][0]["name"] == "read_evidence"
    assert all(not t["mutates"] for t in result["tool_trace"])


def test_agent_refuses_arbitrary_provider_tool_and_recalculations(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    def handler(request):
        return httpx.Response(200, json={"content": [{
            "type": "tool_use", "id": "evil", "name": "run_script", "input": {"command": "x"}
        }]})
    original = httpx.Client
    monkeypatch.setattr(agent.httpx, "Client", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handler)
    ))
    result = agent.respond("execute", "en", REPORT, allow_cloud=True)
    assert result["mode"] == "local_guide"
    assert "run_script" not in str(result)


def test_user_input_bounds_and_unknown_locale():
    with pytest.raises(ValueError):
        agent.respond("x" * 4001, "en", REPORT)
    assert agent.respond("help", "xx", REPORT)["locale"] == "en"


def test_model_cannot_submit_before_receiving_evidence(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    def handler(request):
        return httpx.Response(200, json={"content": [
            {"type": "tool_use", "id": "read", "name": "read_evidence",
             "input": {"evidence_ids": ["score.symbolic"]}},
            {"type": "tool_use", "id": "finish", "name": "submit_answer",
             "input": {"answer": "A claim without seeing the values [score.symbolic]",
                       "evidence_ids": ["score.symbolic"]}},
        ]})
    original = httpx.Client
    monkeypatch.setattr(agent.httpx, "Client", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handler)
    ))
    assert agent.respond("help", "en", REPORT, allow_cloud=True)["mode"] == "local_guide"


def test_tools_declare_authority():
    tools = agent.tool_manifest()
    assert all("deterministic" in tool and "mutates" in tool for tool in tools)
    assert not any(tool["mutates"] for tool in tools)
