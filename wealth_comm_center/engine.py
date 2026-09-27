"""One deterministic service for the UI, agent, map and Stellarium adapters.

All celestial calculations and symbolic rules delegate to the pinned Wealth
Algorithm modules. Swiss Ephemeris has process-global settings: every entry
point uses the same reentrant lock, including its calendar and map work.
"""

from __future__ import annotations

import hashlib
import math
import os
from datetime import date as Date, datetime, time, timezone
from pathlib import Path
from threading import RLock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe

from vendor.wealth_algorithm.wealth_agent.tools import (
    astrocartography, calendar_bridge, cardology, chart, gate_calendar_bridge,
    human_design_gates, mayan_calendar, numerology, scoring, tarot, typology,
)

ENGINE_LOCK = RLock()
ENGINE_VERSION = "wcc-1.0"
UPSTREAM_COMMIT = "1a192eeb2a182f1a32a071d1dd51163936218e2a"
FRAMEWORK_VERSION = "wealth-algorithm-custom-1a192ee"


def normalize_birth(profile: dict) -> datetime:
    """Resolve local civil birth time, rejecting DST gaps and overlaps.

    A timezone must be provided explicitly. Ambiguous records can be entered
    as their verified UTC date/time with timezone UTC; no fold is guessed.
    """
    if not profile.get("birth_time"):
        raise ValueError(
            "Birth time is unknown. Save the profile, then add a verified birth "
            "time to calculate a chart, score, map or sky view. No noon time is assumed."
        )
    try:
        birth_date = Date.fromisoformat(str(profile["birth_date"]))
        birth_time = time.fromisoformat(str(profile["birth_time"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Use a valid birth date and local time (YYYY-MM-DD, HH:MM[:SS]).") from exc
    if not 1800 <= birth_date.year <= 2399:
        raise ValueError("Supported birth dates are 1800 through 2399.")
    if birth_time.tzinfo is not None or birth_time.microsecond:
        raise ValueError("Enter whole-second local birth time without an offset; use the timezone field.")
    try:
        zone = ZoneInfo(str(profile.get("timezone") or ""))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Choose a valid IANA timezone, for example Asia/Tokyo or UTC.") from exc
    naive = datetime.combine(birth_date, birth_time)
    candidates = []
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == naive:
            candidates.append(candidate)
    if not candidates:
        raise ValueError("This local time did not exist because the clocks changed. Verify the birth record.")
    if len(set(candidates)) > 1:
        raise ValueError(
            "This local time is ambiguous because the clocks moved back. "
            "Enter the verified UTC date/time and choose UTC as the timezone."
        )
    _coordinates(profile)
    return candidates[0]


def _coordinates(profile: dict) -> tuple[float, float]:
    try:
        latitude, longitude = float(profile["latitude"]), float(profile["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Birth latitude and longitude are required.") from exc
    if not math.isfinite(latitude) or not -90 < latitude < 90:
        raise ValueError("Latitude must be between -90 and 90 degrees, excluding the exact poles.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180 degrees.")
    return latitude, longitude


def _configure() -> Path:
    ephe_path = Path(os.environ.get("WCC_EPHE_PATH", str(chart.EPHE_DIR))).resolve()
    chart.setup_ephemeris(str(ephe_path))
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    swe.set_topo(0, 0, 0)
    return ephe_path


def _utc_string(instant: datetime) -> str:
    return instant.isoformat().replace("+00:00", "Z")


def _provenance(ephe_path: Path) -> dict:
    files = {}
    for data_file in sorted(ephe_path.glob("*")):
        if data_file.is_file() and data_file.suffix in {".se1", ".txt"}:
            with data_file.open("rb") as stream:
                files[data_file.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "engine_version": ENGINE_VERSION,
        "upstream_commit": UPSTREAM_COMMIT,
        "framework_version": FRAMEWORK_VERSION,
        "swisseph_version": str(swe.version),
        "ephemeris_backends": dict(chart.EPHEMERIS_BACKENDS),
        "ephemeris_files_sha256": files,
        "zodiac": "Upstream custom 13-sign sidereal convention (Lahiri)",
        "houses": "Custom Sagittarius-first sign mapping; not ascendant-based houses",
        "time_basis": "Local civil birth time resolved to UTC; UTC used as UT approximation in calc_ut",
        "calendar_basis": "Birth-date boosts preserved; current-day context is separate",
        "network_downloads": False,
    }


def _warnings(provenance: dict) -> list[str]:
    result = [
        "Symbolic systems and their score are for reflection, not validated predictors of wealth or investment returns.",
        "Custom houses, zodiac boundaries, dignity and metallic-aspect rules follow the source framework; they are not universal conventions.",
        "Calendar suit-element boosts and portions of the cardology karma table are marked provisional in the upstream source.",
    ]
    if any("Moshier" in value for value in provenance["ephemeris_backends"].values()):
        result.append("Some positions used Swiss Ephemeris's built-in Moshier fallback because planetary data files are not installed.")
    return result


def _public_ephemeris_warning(message: str) -> str:
    """Swiss errors may contain absolute server paths; return a safe reason.

    Preserve which calculation was omitted, but do not send filesystem
    diagnostics to an account's report or an external language model.
    """
    if message.startswith("Fixed star '"):
        star = message.split("'", 2)[1]
        if star in chart.STAR_CATALOG:
            return f"Fixed star '{star}' was not resolved from the local star catalog and was omitted."
    body = message.split(":", 1)[0]
    if body == "Chiron":
        return "Chiron could not be computed from locally installed ephemeris data; its dignity contribution was omitted."
    if body in chart.PLANET_CATALOG:
        return f"{body} could not be computed for this date using locally installed ephemeris data."
    return "An ephemeris calculation could not be completed with the configured local data."


def _numerology(name: str | None, birthday: Date, target: Date,
                aspects: list[dict], dignities: list[dict]) -> tuple[dict, float, list[str]]:
    birthday_tuple = (birthday.year, birthday.month, birthday.day)
    life_path = numerology.reduce_number(numerology.date_value(*birthday_tuple))
    attitude = numerology.attitude_number(birthday.month, birthday.day)
    universal = {
        "day": numerology.universal_day(target.year, target.month, target.day),
        "month": numerology.universal_month(target.year, target.month),
        "year": numerology.universal_year(target.year),
    }
    result = {
        "status": "date_only", "life_path": life_path, "attitude": attitude,
        "target_date": target.isoformat(), "universal": universal,
        "personal": {
            "day": numerology.personal_day(universal["day"], attitude),
            "month": numerology.personal_month(universal["month"], attitude),
            "year": numerology.personal_year(universal["year"], attitude),
        },
        "note": "Names are optional and are never inferred from a profile label or automatically romanized.",
    }
    if not name:
        return result, 0.0, []
    ciphers = numerology.load_ciphers(str(numerology.DEFAULT_CIPHERS_JS_PATH))
    letters = [char for char in name.lower() if char.isalpha()]
    # Existing ciphers define their alphabet; do not silently turn an
    # unsupported Japanese/Chinese/Thai/Korean/Vietnamese name into zero.
    if not letters or any(any(ord(char) not in cipher.char_map for char in letters) for cipher in ciphers.values()):
        warning = "Name-based numerology was skipped because the existing cipher alphabets do not support every letter. Date-based numbers remain available; an optional preferred romanization can be supplied."
        result["note"] = warning
        return result, 0.0, [warning]
    num_profile = numerology.compute_numerology_profile(name, birthday_tuple)
    boost, boost_log = numerology.score_numerology_boost(num_profile, aspects, dignities)
    result.update(numerology.numerology_profile_to_dict(num_profile))
    result.update({"status": "available", "boost": boost, "boost_log": boost_log})
    # Preserve a single supplied name as one name part rather than guessing
    # Western first/middle/last-name boundaries for every culture.
    core = numerology.compute_core_numerology_profile(
        name, "", birthday_tuple, target_date=(target.year, target.month, target.day)
    )
    result["core"] = numerology.core_numerology_profile_to_dict(core)
    return result, boost, []


def _cards(birthday: Date) -> tuple[dict, dict]:
    birth_calendar = calendar_bridge.date_to_cosmic_day(birthday.isoformat())
    suit_symbol, rank = birth_calendar["card"]
    suit = {"♥": "H", "♣": "C", "♦": "D", "♠": "S"}.get(suit_symbol)
    if suit is None:
        note = "Joker day is outside the 52-card Master Spread; no card profile is invented."
        return {"status": "joker", "note": note}, {"earth": {"name": "The Fool", "number": 0}}
    profile = cardology.derive_cosmic_cards(f"{rank}{suit}")
    return {"status": "available", "earth_card": profile.earth.symbol, "cards": profile.as_dict()}, tarot.derive_tarot_profile(profile).as_dict()


def _target_date(profile: dict, requested: str | None) -> Date:
    target = Date.fromisoformat(requested) if requested else datetime.now(ZoneInfo(profile["timezone"])).date()
    if not 1800 <= target.year <= 2399:
        raise ValueError("Supported evaluation dates are 1800 through 2399.")
    return target


def build_report(profile: dict, date: str | None = None) -> dict:
    """Calculate a report. No account storage, LLM, network or cache is used."""
    instant = normalize_birth(profile)
    birthday = Date.fromisoformat(profile["birth_date"])
    target = _target_date(profile, date)
    latitude, longitude = _coordinates(profile)
    with ENGINE_LOCK:
        ephe_path = _configure()
        natal = chart.get_natal_chart(
            instant.date().isoformat(), instant.strftime("%H:%M:%S"), latitude, longitude,
            sidereal=True, enneagram_type=profile.get("enneagram_type") or None,
            mbti_type=profile.get("mbti_type") or None,
            numerology_name=profile.get("numerology_name") or None,
        )
        if not {"Sun", "Moon"}.issubset(natal.positions):
            raise ValueError("The ephemeris could not compute the Sun and Moon; a score cannot be produced.")
        aspect_total, aspect_log = scoring.score_aspects(natal.positions, natal.weights, natal.star_positions)
        dignity_total, dignity_log = scoring.score_dignities(
            natal.positions, natal.weights, natal.body_info, natal.dignity_only_bodies
        )
        num_result, num_boost, num_warnings = _numerology(
            profile.get("numerology_name"), birthday, target, aspect_log, dignity_log
        )
        base = scoring.finalize_wealth_score(
            aspect_total, dignity_total, aspect_log, dignity_log, natal.is_day, num_boost
        )
        # All boosts receive complete logs. The presentation cap is applied
        # only after the result is final, so UI and agent scores agree.
        boosted = gate_calendar_bridge.apply_all_cosmic_boosts(
            scoring.score_result_to_dict(base), natal.positions, birthday
        )
        body_wheel = typology.bodies_to_archetype_wheel(natal.positions)
        involved = {body.strip() for item in aspect_log for body in item["pair"].split(" / ")}
        involved.update(item["planet"] for item in dignity_log)
        boosted = typology.apply_typology_boost(
            boosted, natal.enneagram_type, natal.mbti_type, involved, body_wheel
        )
        gates = human_design_gates.bodies_to_gates(natal.positions)
        today_gate = gate_calendar_bridge.day_gate(target)
        cards, tarot_result = _cards(birthday)
        current_jd = chart.get_julian_day(target.year, target.month, target.day, 12.0)
        current_positions, current_retro, current_errors = chart.calc_planets(current_jd, sidereal=True)
        transits = []
        for transit_body, transit_lon in current_positions.items():
            for natal_body, natal_lon in natal.positions.items():
                for aspect_name, orb, _ in scoring.detect_aspects(transit_lon, natal_lon):
                    transits.append({"transit_body": transit_body, "natal_body": natal_body,
                                     "aspect": aspect_name, "orb": round(orb, 5)})
        transits.sort(key=lambda item: item["orb"])
        provenance = _provenance(ephe_path)
        warnings = _warnings(provenance) + [
            _public_ephemeris_warning(message) for message in natal.errors + current_errors
        ] + num_warnings
        bodies = [{
            "name": name, "longitude": natal.positions[name], "sign": info["sign"],
            "house": info["house"], "retrograde": info["retro"],
            "degrees_in_sign": info["deg_in_sign"],
        } for name, info in natal.body_info.items()]
        value = boosted["normalized_score"]
        score = {
            "value": value, "raw": base.raw_score, "aspect": aspect_total,
            "dignity": dignity_total, "numerology_boost": num_boost,
            "base_value": base.normalized_score, "label": scoring.rating_label(value),
            "kind": "experimental", "boosts": boosted["boosts_applied"],
            "calendar_reference_date": birthday.isoformat(),
            "aspect_log": aspect_log[:30], "aspect_log_total": len(aspect_log),
            "dignity_log": dignity_log,
        }
        if value == 100:
            warnings.append("The symbolic score reached its configured 100-point cap; it is not a probability or a guarantee.")
        calendar_result = {
            "birth": calendar_bridge.date_to_cosmic_day(birthday.isoformat()),
            "today": calendar_bridge.date_to_cosmic_day(target.isoformat()),
            "day_gate": today_gate, "date": target.isoformat(),
            "transits": transits[:30], "transit_count": len(transits),
            "snapshot_utc": f"{target.isoformat()}T12:00:00Z",
            "snapshot_note": "Noon-UTC planetary snapshot, not a prediction of exact event times. Transits do not change the natal score.",
            "current_positions": [{"name": name, "longitude": lon, "retrograde": current_retro[name]}
                                  for name, lon in current_positions.items()],
        }
        systems = {
            "numerology": num_result,
            "typology": {"enneagram_type": natal.enneagram_type, "enneagram_wing": natal.enneagram_wing,
                         "mbti_type": natal.mbti_type, "mbti_variant": natal.mbti_variant,
                         "self_reported": True, "archetype_wheel": body_wheel},
            "gates": gates, "calendar": calendar_result,
            "mayan": {"birth": mayan_calendar.date_to_tzolkin(birthday),
                      "today": mayan_calendar.date_to_tzolkin(target),
                      "tree_of_life": mayan_calendar.tree_of_life(birthday)},
            "cardology": cards, "tarot": tarot_result,
        }
        evidence = [
            {"id": "score.symbolic", "label": "Symbolic framework score", "value": value, "kind": "experimental"},
            {"id": "score.aspects", "label": "Metallic/aspect contribution", "value": aspect_total, "kind": "derived"},
            {"id": "score.dignity", "label": "Custom dignity contribution", "value": dignity_total, "kind": "interpretive"},
            {"id": "calendar.today", "label": "Custom calendar date", "value": calendar_result["today"], "kind": "derived"},
            {"id": "calendar.day_gate", "label": "Noon UTC Sun gate", "value": today_gate, "kind": "derived"},
            {"id": "numerology.life_path", "label": "Date-based life path", "value": num_result["life_path"], "kind": "derived"},
            {"id": "mayan.birth", "label": "Tzolkin birth-date mapping", "value": systems["mayan"]["birth"], "kind": "derived"},
            {"id": "cardology.birth", "label": "Provisional cardology mapping", "value": cards, "kind": "experimental"},
        ]
        for body in bodies:
            evidence.append({"id": f"chart.{body['name'].lower().replace(' ', '_')}.longitude",
                             "label": f"{body['name']} sidereal longitude", "value": body["longitude"],
                             "kind": "computed" if body["name"] in chart.PLANET_CATALOG else "derived"})
        return {
            "schema_version": "1.0", "profile_id": profile.get("id"),
            "generated_at": _utc_string(datetime.now(timezone.utc)),
            "birth_utc": _utc_string(instant), "evaluation_date": target.isoformat(),
            "score": score,
            "chart": {"bodies": bodies, "ascendant": natal.ascendant, "is_day_chart": natal.is_day,
                      "julian_day_utc": natal.julian_day, "fixed_stars": natal.star_positions,
                      "dignity_only_bodies": natal.dignity_only_bodies,
                      "zodiac": provenance["zodiac"], "house_system": provenance["houses"]},
            "systems": systems, "evidence": evidence,
            "warnings": list(dict.fromkeys(warnings)), "provenance": provenance,
        }


def build_map(profile: dict) -> dict:
    """GeoJSON longitude/latitude lines; scoring never consumes this map."""
    instant = normalize_birth(profile)
    with ENGINE_LOCK:
        ephe_path = _configure()
        lines = astrocartography.compute_lines(instant.date().isoformat(), instant.strftime("%H:%M:%S"))
        features = []
        for name, body in lines.items():
            curves = {
                "MC": [[(body.mc_longitude, -89), (body.mc_longitude, 89)]],
                "IC": [[(body.ic_longitude, -89), (body.ic_longitude, 89)]],
                "AC": astrocartography.split_on_wraparound(body.ac_curve),
                "DC": astrocartography.split_on_wraparound(body.dc_curve),
            }
            for line_type, segments in curves.items():
                valid = [[list(point) for point in segment] for segment in segments if len(segment) >= 2]
                if not valid:
                    continue
                features.append({
                    "type": "Feature", "id": f"{name}-{line_type}",
                    "properties": {"body": name, "line_type": line_type, "angle": line_type, "kind": "computed",
                                   "label": f"{name} {line_type}",
                                   "circumpolar_gaps": body.ac_gaps if line_type == "AC" else body.dc_gaps if line_type == "DC" else []},
                    "geometry": {"type": "MultiLineString", "coordinates": valid},
                })
        provenance = _provenance(ephe_path)
        return {"type": "FeatureCollection", "features": features,
                "profile_id": profile.get("id"), "birth_utc": _utc_string(instant),
                "provenance": provenance, "warnings": _warnings(provenance) + [
                    "AC/DC lines omit circumpolar regions and split at the date line. Sampling is 2 degrees latitude; lines are not financial forecasts."
                ]}


def build_sky_state(profile: dict) -> dict:
    """Provider-neutral observer/time contract; no renderer feeds the score."""
    instant = normalize_birth(profile)
    latitude, longitude = _coordinates(profile)
    with ENGINE_LOCK:
        julian_day = chart.get_julian_day(instant.year, instant.month, instant.day,
                                         instant.hour + instant.minute / 60 + instant.second / 3600)
    return {"schema_version": "1.0", "profile_id": profile.get("id"),
            "utc": _utc_string(instant), "julian_day_utc": julian_day,
            "latitude": latitude, "longitude": longitude, "altitude": 0,
            "selected_body": "Sun", "source": "python/swisseph",
            "time_scale": "UTC (UT approximation for Swiss calc_ut)",
            "warnings": ["Stellarium is a visual companion. Its render-time ephemerides never replace the Python calculation results."]}
