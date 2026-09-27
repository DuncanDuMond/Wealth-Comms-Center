import copy
import json
from xml.etree import ElementTree

import pytest

from wealth_command_center.cosmic_cards import CosmicCard, resolve_card, render_svg


FIXTURE = {
    "profile_id": "not-public", "profile": {"name": "NOT-PUBLIC"},
    "chart": {"zodiac": "custom-test-frame", "bodies": [
        {"name": "Sun", "longitude": 143.25, "sign": "Leo", "house": 9,
         "retrograde": False, "degrees_in_sign": 23.25},
        {"name": "Jupiter", "longitude": 90.5, "sign": "Gemini", "house": 7,
         "retrograde": True, "degrees_in_sign": 5.5},
    ]},
    "evidence": [
        {"id": "chart.sun.longitude", "value": 143.25, "kind": "computed"},
        {"id": "chart.jupiter.longitude", "value": 90.5, "kind": "computed"},
    ],
    "systems": {"gates": {"Sun": {"gate": 33, "line": 2}, "Jupiter": {"gate": 15, "line": 3}}},
    "provenance": {"engine_version": "fixture-1", "framework_version": "fixture-1", "name": "NOT-PUBLIC"},
}


def test_sun_card_uses_report_values_without_personal_examples():
    before = copy.deepcopy(FIXTURE)
    card = resolve_card(FIXTURE)
    assert CosmicCard.model_validate(card)
    assert card["entity"]["canonical_name"] == "Sun"
    assert card["placement"]["longitude"] == 143.25
    assert card["correspondences"]["gate"]["gate"] == 33
    assert card["correspondences"]["tarot"] is None
    assert card["correspondences"]["card_rank"] is None
    assert "NOT-PUBLIC" not in json.dumps(card)
    assert "not-public" not in json.dumps(card)
    assert FIXTURE == before


def test_generic_entity_uses_same_resolver_without_sun_correspondences():
    card = resolve_card(FIXTURE, "jupiter")
    assert card["placement"]["longitude"] == 90.5
    assert card["entity"]["editorial_element"] is None
    assert card["entity"]["archetypes"] == []
    assert card["correspondences"]["gate"]["gate"] == 15
    assert card["visual"]["motif"] == "orbit"


@pytest.mark.parametrize("locale", ["en", "ja", "zh-CN", "th", "ko", "vi"])
def test_all_locales_render_valid_self_contained_svg(locale):
    card = resolve_card(FIXTURE, locale=locale)
    svg = render_svg(card)
    root = ElementTree.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["lang"] == locale
    assert card["title"] in svg
    assert "<script" not in svg
    assert "http" not in svg.replace("http://www.w3.org/2000/svg", "")


def test_absent_or_disagreeing_evidence_remains_missing():
    fixture = copy.deepcopy(FIXTURE)
    fixture["evidence"][0]["value"] = 20
    card = resolve_card(fixture)
    assert card["placement"] is None
    assert card["correspondences"]["gate"] is None
    assert card["warnings"]
    assert resolve_card({})["placement"] is None


def test_svg_escapes_all_display_text():
    card = resolve_card(FIXTURE)
    card["title"] = '<script>alert("x")</script>'
    card["labels"]["archetypes"] = '"/><image href="https://evil.test"/>'
    svg = render_svg(card)
    root = ElementTree.fromstring(svg)
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
    assert not list(root.iter("{http://www.w3.org/2000/svg}image"))


def test_fingerprint_changes_with_facts_or_framework_not_timestamp():
    baseline = resolve_card(FIXTURE)["provenance"]["fingerprint"]
    fixture = copy.deepcopy(FIXTURE)
    fixture["generated_at"] = "2030-01-01T00:00:00Z"
    assert resolve_card(fixture)["provenance"]["fingerprint"] == baseline
    fixture["provenance"]["framework_version"] = "fixture-2"
    assert resolve_card(fixture)["provenance"]["fingerprint"] != baseline
    assert resolve_card(FIXTURE, locale="ja")["provenance"]["fingerprint"] != baseline


def test_sun_reference_fixture_golden_fingerprint():
    # A stable synthetic fixture, never the personal chart from the discussion.
    assert resolve_card(FIXTURE)["provenance"]["fingerprint"] == (
        "320481f852868f67aea2443ea836c4a28555251d1979dbc57b0bbc65f9128d75"
    )


def test_unsupported_entity_rejected_not_silently_substituted():
    with pytest.raises(ValueError):
        resolve_card(FIXTURE, "sun-spirit-49-king-of-spades")


def test_real_engine_report_card_and_agent_agree():
    from wealth_command_center.engine import build_report
    from wealth_command_center.agent import respond
    profile = {"birth_date": "1990-01-15", "birth_time": "12:00:00", "timezone": "Asia/Tokyo",
               "latitude": 35.68, "longitude": 139.76}
    report = build_report(profile, "2026-09-26")
    card = resolve_card(report)
    sun = next(body for body in report["chart"]["bodies"] if body["name"] == "Sun")
    assert card["placement"]["longitude"] == sun["longitude"]
    assert card["correspondences"]["gate"]["gate"] == report["systems"]["gates"]["Sun"]["gate"]
    answer = respond("explain my score", "en", report)
    assert answer["evidence"][0]["value"] == report["score"]["value"]
    assert format(report["score"]["value"], ".6g") in answer["answer"]
