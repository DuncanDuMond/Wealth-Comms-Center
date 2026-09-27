"""Synthetic geometry fixtures are not presented as real stellar boundaries."""

import random

import pytest

from wealth_command_center.boundaries import (
    boundary_status, classify_longitude, constellation_intersections,
    derive_stellar_boundaries, stellar_group_extent,
)


@pytest.fixture
def frame():
    return {"id": "test-only", "epoch_jd": 2451545, "epoch_scale": "TT",
            "reference_frame": "synthetic test ecliptic", "origin_definition": "test zero",
            "origin_longitude_deg": 0}


@pytest.fixture
def groups():
    return [{"name": f"test-{index}", "longitudes_deg": [index * 360 / 27 - 1, index * 360 / 27 + 1]}
            for index in range(27)]


def test_star_extrema_unwrap_instead_of_using_label_order():
    assert stellar_group_extent([1, 359, 0]) == stellar_group_extent([359, 0, 1])
    result = stellar_group_extent([1, 359, 0])
    assert result["start_deg"] == 359
    assert result["end_unwrapped_deg"] == 361
    assert result["span_deg"] == 2


def test_midpoint_sectors_do_not_depend_on_input_group_order(groups, frame):
    first = derive_stellar_boundaries(groups, frame)
    random.Random(5).shuffle(groups)
    second = derive_stellar_boundaries(groups, frame)
    assert first == second
    sectors = first["sectors"]
    assert len(sectors) == 27
    assert sum(sector["span_deg"] for sector in sectors) == pytest.approx(360)
    assert classify_longitude(0, sectors)["name"] == "test-0"
    assert classify_longitude(360, sectors) == classify_longitude(0, sectors)


def test_every_boundary_is_half_open_and_padas_partition_sector(groups, frame):
    sectors = derive_stellar_boundaries(groups, frame)["sectors"]
    for sector in sectors:
        assert classify_longitude(sector["start_deg"], sectors)["name"] == sector["name"]
        assert classify_longitude(sector["end_deg"], sectors)["name"] != sector["name"]
        for pada in range(1, 5):
            middle = sector["start_deg"] + (pada - 0.5) * sector["span_deg"] / 4
            result = classify_longitude(middle, sectors)
            assert result["name"] == sector["name"]
            assert result["pada"] == pada


def test_origin_is_explicit_and_applied_once(groups, frame):
    frame["origin_longitude_deg"] = 27
    sectors = derive_stellar_boundaries(groups, frame)["sectors"]
    assert classify_longitude(-27, sectors)["name"] == "test-0"
    with pytest.raises(ValueError, match="explicit"):
        derive_stellar_boundaries(groups, {})


def test_overlap_and_missing_catalog_regions_are_rejected(groups, frame):
    groups[1]["longitudes_deg"] = groups[0]["longitudes_deg"]
    with pytest.raises(ValueError, match="overlap"):
        derive_stellar_boundaries(groups, frame)
    groups = [{"name": str(index), "longitudes_deg": [index]} for index in range(27)]
    with pytest.raises(ValueError, match="gap"):
        derive_stellar_boundaries(groups, frame)
    with pytest.raises(ValueError, match="wrapping"):
        stellar_group_extent([0, 120, 240])


def test_intersections_preserve_area_and_wraparound(groups, frame):
    sectors = derive_stellar_boundaries(groups, frame)["sectors"]
    constellations = [{"name": f"region-{index}", "start_deg": index * 30,
                       "end_deg": (index + 1) * 30 % 360} for index in range(12)]
    intersections = constellation_intersections(sectors, constellations)
    assert sum(item["span_deg"] for item in intersections) == pytest.approx(360)
    assert all(0 <= item["start_deg"] < item["end_deg"] <= 360 for item in intersections)
    crossing = [item for item in intersections if item["nakshatra"] == "test-0"]
    assert {item["constellation"] for item in crossing} == {"region-0", "region-11"}


def test_missing_frame_and_memberships_are_not_published_as_boundaries():
    result = boundary_status()
    assert result["status"] == "incomplete"
    assert result["active_in_chart"] is False
    assert result["group_count"] == 27
    assert result["derived"] is None
    assert result["frame"] is None
    assert "Krittika" in result["unverified_groups"]
    assert len(result["blockers"]) >= 3


def test_verified_explicit_catalog_can_be_derived(groups, frame):
    for group in groups:
        group["membership_status"] = "verified"
    result = boundary_status({"id": "synthetic-test", "review_status": "verified", "frame": frame, "groups": groups})
    assert result["status"] == "ready"
    assert result["active_in_chart"] is False
    assert result["derived"]["frame"] == frame


@pytest.mark.parametrize("longitude", [float("nan"), float("inf"), True, "invalid"])
def test_invalid_longitudes_are_rejected(longitude):
    with pytest.raises(ValueError, match="finite"):
        stellar_group_extent([longitude])
