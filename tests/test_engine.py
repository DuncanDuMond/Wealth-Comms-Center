"""Real Swiss Ephemeris integration, time-boundary and serialization checks."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
import swisseph as swe

from wealth_command_center.engine import (
    ENGINE_LOCK, build_map, build_report, build_sky_state, normalize_birth,
)
from vendor.wealth_algorithm.wealth_agent.tools import astrocartography, scoring


@pytest.fixture
def profile():
    return {"id": "fixture", "name": "Sample profile", "birth_date": "1990-01-01",
            "birth_time": "12:34:56", "timezone": "Asia/Tokyo", "latitude": 35.68,
            "longitude": 139.69, "place_name": "Tokyo", "numerology_name": None,
            "enneagram_type": None, "mbti_type": None}


def test_explicit_zone_and_fractional_hour_offsets(profile):
    assert normalize_birth(profile) == datetime(1990, 1, 1, 3, 34, 56, tzinfo=timezone.utc)
    profile.update(timezone="Asia/Kathmandu", birth_time="05:45:00")
    assert normalize_birth(profile) == datetime(1990, 1, 1, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("changes,message", [
    ({"birth_time": None}, "unknown"),
    ({"timezone": ""}, "IANA"),
    ({"birth_date": "2021-03-14", "birth_time": "02:30", "timezone": "America/New_York"}, "did not exist"),
    ({"birth_date": "2021-11-07", "birth_time": "01:30", "timezone": "America/New_York"}, "ambiguous"),
    ({"birth_date": "2021-02-30"}, "valid birth"),
    ({"latitude": float("nan")}, "Latitude"),
    ({"longitude": 181}, "Longitude"),
    ({"birth_time": "12:30:00+09:00"}, "without an offset"),
])
def test_time_and_coordinate_failures_are_actionable(profile, changes, message):
    profile.update(changes)
    with pytest.raises(ValueError, match=message):
        normalize_birth(profile)


def test_report_uses_real_swiss_positions_and_explicit_evidence(profile):
    result = build_report(profile, date="2026-09-26")
    # Independently request the Sun from Swiss Ephemeris, not the report's
    # chart helper. The external time oracle is Tokyo -> UTC above.
    with ENGINE_LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        jd = swe.julday(1990, 1, 1, 3 + 34 / 60 + 56 / 3600)
        expected, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL)
    bodies = {body["name"]: body for body in result["chart"]["bodies"]}
    assert bodies["Sun"]["longitude"] == pytest.approx(expected[0], abs=1e-10)
    assert 14 == len(bodies)
    assert all(0 <= body["longitude"] < 360 for body in bodies.values())
    assert 0 <= result["score"]["value"] <= 100
    assert result["score"]["label"] == scoring.rating_label(result["score"]["value"])
    assert result["score"]["raw"] == pytest.approx(
        result["score"]["aspect"] + result["score"]["dignity"] + result["score"]["numerology_boost"], abs=0.001
    )
    assert result["birth_utc"] == "1990-01-01T03:34:56Z"
    assert result["provenance"]["ephemeris_backends"]
    assert result["provenance"]["network_downloads"] is False
    assert {"numerology", "gates", "mayan", "cardology", "tarot", "typology", "calendar"} == set(result["systems"])
    ids = [item["id"] for item in result["evidence"]]
    assert len(ids) == len(set(ids))
    assert all(item["kind"] in {"computed", "derived", "interpretive", "experimental"} for item in result["evidence"])
    json.dumps(result, allow_nan=False)


def test_calendar_preserves_local_birthday_across_utc_rollover(profile):
    profile.update(birth_time="00:30")
    result = build_report(profile, "2026-09-26")
    assert result["birth_utc"].startswith("1989-12-31")
    assert result["systems"]["calendar"]["birth"]["gregorian_date"] == "1990-01-01"
    assert result["score"]["calendar_reference_date"] == "1990-01-01"


def test_multilingual_name_is_not_silently_scored_as_zero(profile):
    profile.update(name="山田花子", numerology_name="山田花子")
    result = build_report(profile, "2026-09-26")
    assert result["systems"]["numerology"]["status"] == "date_only"
    assert result["systems"]["numerology"]["life_path"] > 0
    assert result["score"]["numerology_boost"] == 0
    assert any("romanization" in warning for warning in result["warnings"])


def test_supported_name_typology_and_joker_day(profile):
    profile.update(birth_date="1990-12-18", numerology_name="Alex", enneagram_type="7w8", mbti_type="INTJ-A")
    result = build_report(profile, "2026-09-26")
    assert result["systems"]["numerology"]["status"] == "available"
    assert result["systems"]["typology"]["enneagram_wing"] == 8
    assert result["systems"]["typology"]["mbti_variant"] == "A"
    assert result["systems"]["cardology"]["status"] == "joker"
    assert result["systems"]["tarot"]["earth"]["name"] == "The Fool"


def test_polar_latitude_has_ascendant_without_fabricated_placidus_houses(profile):
    profile["latitude"] = 78.2
    result = build_report(profile, "2026-09-26")
    assert 0 <= result["chart"]["ascendant"] < 360
    assert "Custom Sagittarius" in result["chart"]["house_system"]


def test_map_geojson_seams_bounds_and_real_meridian(profile):
    result = build_map(profile)
    assert result["type"] == "FeatureCollection"
    assert {feature["properties"]["line_type"] for feature in result["features"]} == {"MC", "IC", "AC", "DC"}
    assert len(result["features"]) == 40
    for feature in result["features"]:
        for segment in feature["geometry"]["coordinates"]:
            assert len(segment) >= 2
            assert all(-180 <= lon <= 180 and -89 <= lat <= 89 for lon, lat in segment)
            assert all(abs(a[0] - b[0]) <= 180 for a, b in zip(segment, segment[1:]))
    sky = build_sky_state(profile)
    with ENGINE_LOCK:
        xx, _ = swe.calc_ut(sky["julian_day_utc"], swe.SUN, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL)
        expected = (xx[0] - swe.sidtime(sky["julian_day_utc"]) * 15 + 180) % 360 - 180
    sun_mc = next(feature for feature in result["features"] if feature["id"] == "Sun-MC")
    assert sun_mc["geometry"]["coordinates"][0][0][0] == pytest.approx(expected, abs=0.0001)
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("step", [0, -1, float("nan"), 0.00001])
def test_map_sampling_cannot_loop_forever(step):
    with pytest.raises(ValueError, match="sampling"):
        astrocartography.compute_lines("1990-01-01", "00:00", lat_step=step)


def test_map_and_other_profiles_do_not_change_natal_results(profile):
    expected = build_report(profile, "2026-09-26")
    other = {**profile, "id": "other", "birth_date": "2001-07-01", "timezone": "Asia/Bangkok"}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(build_map, other), pool.submit(build_report, other, "2026-09-26"),
                   pool.submit(build_report, profile, "2026-09-26")]
        outputs = [future.result() for future in futures]
    assert outputs[2]["chart"] == expected["chart"]
    assert outputs[2]["score"] == expected["score"]
    assert outputs[2]["provenance"] == expected["provenance"]


def test_no_runtime_network_when_ephemeris_files_missing(profile, monkeypatch, tmp_path):
    monkeypatch.setenv("WCC_EPHE_PATH", str(tmp_path))
    result = build_report(profile, "2026-09-26")
    assert result["provenance"]["ephemeris_files_sha256"] == {}
    assert any("Moshier" in value for value in result["provenance"]["ephemeris_backends"].values())
    assert any("Chiron" in warning for warning in result["warnings"])
    assert all("PATH" not in warning and str(tmp_path) not in warning for warning in result["warnings"])
    assert result["provenance"]["network_downloads"] is False
    assert list(tmp_path.iterdir()) == []
