"""Independent, versionable circular-boundary algebra for custom overlays.

This module deliberately does not compute stellar positions, invent a zodiac
zero, or attach incomplete candidate memberships to the live Lahiri chart.
Inputs are explicit star longitudes in a declared frame and epoch. All sectors
are left-inclusive/right-exclusive and are divided into four equal padas.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "registry" / "nakshatra-candidate.json"


def _degree(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("A longitude must be a finite number of degrees.")
    try:
        degree = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("A longitude must be a finite number of degrees.") from exc
    if not math.isfinite(degree):
        raise ValueError("A longitude must be a finite number of degrees.")
    return degree % 360.0


def validate_frame(frame: dict) -> dict:
    """No implicit origin, epoch, timescale or reference-frame convention."""
    required = ("id", "epoch_jd", "epoch_scale", "reference_frame", "origin_definition", "origin_longitude_deg")
    if not isinstance(frame, dict) or any(frame.get(key) is None for key in required):
        raise ValueError("Custom boundaries require an explicit frame, epoch, timescale and origin.")
    if any(not isinstance(frame[key], str) or not frame[key].strip()
           for key in ("id", "reference_frame", "origin_definition")):
        raise ValueError("Frame id, reference frame and origin definition must be nonempty text.")
    try:
        epoch = float(frame["epoch_jd"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Epoch must be a finite Julian day.") from exc
    if not math.isfinite(epoch) or frame["epoch_scale"] not in {"TT", "UT", "UTC"}:
        raise ValueError("Epoch must be a finite Julian day with an explicit TT, UT or UTC timescale.")
    return {**frame, "epoch_jd": epoch, "origin_longitude_deg": _degree(frame["origin_longitude_deg"])}


def stellar_group_extent(longitudes: list[float], *, max_span_deg: float = 45.0) -> dict:
    """Find the smallest circular arc containing a group's actual stars.

    Cut at the largest empty gap, then take extrema in the unwrapped arc.
    Star label/alphabetical order has no effect. A default 45-degree maximum
    is an explicit input-sanity guard, not an astronomical boundary claim.
    """
    if not math.isfinite(max_span_deg) or not 0 < max_span_deg < 180:
        raise ValueError("Maximum group span must be between 0 and 180 degrees.")
    values = sorted({_degree(value) for value in longitudes})
    if not values:
        raise ValueError("Each stellar group needs at least one resolved longitude.")
    gaps = [(values[(index + 1) % len(values)] + (360 if index == len(values) - 1 else 0) - value)
            for index, value in enumerate(values)]
    cut = (max(range(len(gaps)), key=gaps.__getitem__) + 1) % len(values)
    start = values[cut]
    unwrapped = sorted(value if value >= start else value + 360 for value in values)
    span = unwrapped[-1] - unwrapped[0]
    if span > max_span_deg:
        raise ValueError("Stellar group spans an implausibly large wrapping arc; verify membership and frame.")
    return {"start_deg": start, "end_unwrapped_deg": start + span,
            "span_deg": span, "resolved_star_count": len(values)}


def derive_stellar_boundaries(groups: list[dict], frame: dict, *,
                               max_group_span_deg: float = 45.0,
                               max_intergroup_gap_deg: float = 60.0) -> dict:
    """Derive 27 sectors from midpoint gaps between adjacent stellar edges.

    Each group has a unique name and longitudes_deg resolved in frame's
    reference coordinate system. The explicit origin is subtracted once.
    Group ordering is derived geometrically, never from input label order.
    """
    frame = validate_frame(frame)
    if len(groups) != 27:
        raise ValueError("Exactly 27 stellar groups are required.")
    if not math.isfinite(max_intergroup_gap_deg) or not 0 < max_intergroup_gap_deg < 180:
        raise ValueError("Maximum intergroup gap must be between 0 and 180 degrees.")
    names = [group.get("name") for group in groups]
    if any(not isinstance(name, str) or not name.strip() for name in names) or len(set(names)) != 27:
        raise ValueError("All 27 stellar-group names must be nonempty and unique.")
    extents = []
    for group in groups:
        transformed = [_degree(value) - frame["origin_longitude_deg"] for value in group.get("longitudes_deg", [])]
        extent = stellar_group_extent(transformed, max_span_deg=max_group_span_deg)
        extents.append({"name": group["name"], **extent})
    extents.sort(key=lambda item: item["start_deg"])
    midpoints = []
    for index, extent in enumerate(extents):
        following_start = extents[(index + 1) % 27]["start_deg"] + (360 if index == 26 else 0)
        gap = following_start - extent["end_unwrapped_deg"]
        if gap < 0:
            raise ValueError("Stellar group extents overlap; no midpoint boundary is unambiguous.")
        if gap > max_intergroup_gap_deg:
            raise ValueError("Intergroup or wrapping gap is too large; verify catalog completeness.")
        midpoints.append((extent["end_unwrapped_deg"] + gap / 2) % 360)
    sectors = []
    for index, extent in enumerate(extents):
        start, end = midpoints[index - 1], midpoints[index]
        sectors.append({"name": extent["name"], "start_deg": start, "end_deg": end,
                        "span_deg": (end - start) % 360, "star_extent": extent})
    _validate_ring(sectors, expected_count=27)
    return {"schema_version": "1.0", "method": "midpoints-between-unwrapped-stellar-extents",
            "frame": frame, "sectors": sectors,
            "guards": {"max_group_span_deg": max_group_span_deg,
                       "max_intergroup_gap_deg": max_intergroup_gap_deg},
            "note": "Derived from supplied longitudes; this does not certify source membership or astrometric accuracy."}


def _validate_ring(sectors: list[dict], expected_count: int | None = None) -> list[dict]:
    if not sectors or (expected_count is not None and len(sectors) != expected_count):
        raise ValueError(f"Expected {expected_count or 'at least one'} sectors in a complete ring.")
    names = [sector.get("name") for sector in sectors]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Sector names must be nonempty and unique.")
    normalized = []
    for sector in sectors:
        start, end = _degree(sector.get("start_deg")), _degree(sector.get("end_deg"))
        span = (end - start) % 360
        if span == 0:
            raise ValueError("Zero-width or full-circle sectors are not allowed.")
        if "span_deg" in sector and not math.isclose(float(sector["span_deg"]), span, abs_tol=1e-8):
            raise ValueError("Sector span does not match its boundary coordinates.")
        normalized.append({**sector, "start_deg": start, "end_deg": end, "span_deg": span})
    ordered = sorted(normalized, key=lambda item: item["start_deg"])
    for index, sector in enumerate(ordered):
        following = ordered[(index + 1) % len(ordered)]["start_deg"]
        if not math.isclose(sector["end_deg"], following, abs_tol=1e-8):
            raise ValueError("Sectors have a gap or overlap instead of a complete circular partition.")
    if not math.isclose(sum(item["span_deg"] for item in ordered), 360, abs_tol=1e-7):
        raise ValueError("Sector widths must cover exactly 360 degrees.")
    return normalized


def classify_longitude(longitude: float, sectors: list[dict]) -> dict:
    """Classify a longitude already expressed in the sectors' custom frame."""
    longitude = _degree(longitude)
    for sector in _validate_ring(sectors, expected_count=27):
        offset = (longitude - sector["start_deg"]) % 360
        if offset < sector["span_deg"]:
            pada = min(4, int(offset / (sector["span_deg"] / 4)) + 1)
            return {"name": sector["name"], "pada": pada, "longitude_deg": longitude,
                    "start_deg": sector["start_deg"], "end_deg": sector["end_deg"],
                    "offset_deg": offset, "pada_width_deg": sector["span_deg"] / 4,
                    "boundary_convention": "left-inclusive, right-exclusive"}
    raise ValueError("Longitude could not be classified; verify sector precision.")


def _pieces(sector: dict) -> list[tuple[float, float]]:
    start = sector["start_deg"]
    end = start + sector["span_deg"]
    return [(start, min(end, 360))] + ([(0, end - 360)] if end > 360 else [])


def constellation_intersections(sectors: list[dict], constellations: list[dict]) -> list[dict]:
    """Intersect two declared partitions in the SAME frame and epoch.

    The caller owns that frame equality check; no IAU dates or approximate
    screenshot ranges are silently treated as ecliptic boundaries.
    """
    sectors = _validate_ring(sectors, expected_count=27)
    constellations = _validate_ring(constellations)
    overlaps = []
    for sector in sectors:
        for constellation in constellations:
            for left_start, left_end in _pieces(sector):
                for right_start, right_end in _pieces(constellation):
                    start, end = max(left_start, right_start), min(left_end, right_end)
                    if end > start:
                        overlaps.append({"nakshatra": sector["name"], "constellation": constellation["name"],
                                         "start_deg": start, "end_deg": end, "span_deg": end - start})
    return overlaps


def boundary_status(catalog: dict | None = None) -> dict:
    """Candidate metadata is not a ready-to-use degree table."""
    if catalog is None:
        with CATALOG_PATH.open(encoding="utf-8") as stream:
            catalog = json.load(stream)
    groups = catalog.get("groups", [])
    blockers = []
    if catalog.get("review_status") != "verified":
        blockers.append("Candidate memberships are unverified conversation transcriptions.")
    if len(groups) != 27:
        blockers.append("Exactly 27 candidate stellar groups are required.")
    unresolved = [group.get("name", "unnamed") for group in groups if group.get("membership_status") != "verified"]
    if unresolved:
        blockers.append("Each stellar membership and catalog identifier must be verified, including cluster-membership rules.")
    try:
        frame = validate_frame(catalog.get("frame"))
    except ValueError as exc:
        frame = None
        blockers.append(str(exc))
    if any(not group.get("longitudes_deg") for group in groups):
        blockers.append("Canonical stellar longitudes have not been resolved at the declared epoch.")
    derived = None
    if not blockers:
        try:
            derived = derive_stellar_boundaries(groups, frame)
        except ValueError as exc:
            blockers.append(str(exc))
    return {"status": "incomplete" if blockers else "ready", "active_in_chart": False,
            "method_ready": True, "catalog_id": catalog.get("id"), "group_count": len(groups),
            "source": catalog.get("source"), "frame": frame, "blockers": blockers,
            "unverified_groups": unresolved, "derived": derived,
            "note": "Optional custom overlay only. Existing Python/Lahiri calculations are unchanged; no boundaries are inferred from screenshot dates."}
