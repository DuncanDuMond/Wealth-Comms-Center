"""One-way presentation adapter. No ephemeris or scoring calculations live here."""

from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

PHYSICAL_BODIES = frozenset({
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"
})
_sync_lock = asyncio.Lock()


class StellariumUnavailable(RuntimeError):
    """Safe public error; never contains a password or remote response body."""


def stellarium_enabled() -> bool:
    return os.getenv("STELLARIUM_ENABLED", "false").lower() == "true"


def _number(state: dict, name: str, low: float, high: float, default=None) -> float:
    value = state.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid sky state: {name}")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid sky state: {name}")
    return float(value)


def _validate(state: dict, body: str) -> dict:
    if body not in PHYSICAL_BODIES:
        raise ValueError("Choose a supported physical body; symbolic points are not sky objects.")
    if not isinstance(state, dict):
        raise ValueError("A canonical engine sky state is required.")
    try:
        instant = datetime.fromisoformat(state["utc"].replace("Z", "+00:00"))
        if instant.utcoffset() is None:
            raise ValueError("Timezone required")
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Invalid sky state: timezone-aware utc is required") from exc
    return {
        "utc": instant.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "julian_day_utc": _number(state, "julian_day_utc", 2000000, 3000000),
        "latitude": _number(state, "latitude", -90, 90),
        "longitude": _number(state, "longitude", -180, 180),
        "altitude": _number(state, "altitude", -1000, 100000, 0),
    }


def make_script(state: dict, body: str = "Jupiter") -> str:
    """Return a safe, user-run .ssc file. This function never launches Stellarium.

    ISO strings have no zone suffix because setDate's second argument selects UTC.
    The inherited Julian day is metadata, not a second calculation of the instant.
    """
    checked = _validate(state, body)
    date_arg = json.dumps(checked["utc"].removesuffix("Z"))
    body_arg = json.dumps(body)
    return (
        "// Name: Wealth Command Center sky view\n"
        "// Description: One-way visualization of an engine-owned instant and place.\n"
        "// No score is calculated or changed by this script.\n"
        f"// Engine Julian day (UTC approximation): {checked['julian_day_utc']}\n"
        "core.setTimeRate(0);\n"
        f"core.setObserverLocation({checked['longitude']}, {checked['latitude']}, "
        f"{checked['altitude']}, 0, \"Wealth Command Center\", \"Earth\");\n"
        f"core.setDate({date_arg}, \"utc\", false);\n"
        f"core.selectObjectByName({body_arg}, true);\n"
        f"core.moveToObject({body_arg}, 0);\n"
    )


def _local_url() -> str:
    # Canonicalize localhost to a literal IP; no DNS lookup or environment proxies.
    # Deliberately reject general private/LAN addresses and non-default loopbacks.
    try:
        url = urlsplit(os.getenv("STELLARIUM_URL", "http://127.0.0.1:8090"))
        port = url.port or 8090
        if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}
                or url.username is not None or url.password is not None
                or url.path not in {"", "/"} or url.query or url.fragment
                or url.port == 0 or not 1 <= port <= 65535):
            raise ValueError("Not loopback")
    except ValueError as exc:
        raise ValueError("STELLARIUM_URL must be an HTTP loopback origin without credentials or paths.") from exc
    host = "[::1]" if url.hostname == "::1" else "127.0.0.1"
    return f"http://{host}:{port}"


async def send_to_stellarium(state: dict, body: str = "Jupiter") -> dict:
    """Explicit-action desktop sync for a local installation only.

    Calls are serialized because a desktop viewer has one mutable observer. Public
    servers must leave this feature disabled; loopback refers to the API host, not
    a website visitor's computer. Never invoke this from the language model.
    """
    checked = _validate(state, body)
    if not stellarium_enabled():
        raise StellariumUnavailable("Desktop control is disabled. Export a Stellarium script instead.")
    base = _local_url()
    password = os.getenv("STELLARIUM_PASSWORD")
    auth = httpx.BasicAuth("", password) if password else None
    try:
        async with asyncio.timeout(15):
            async with _sync_lock:
                async with httpx.AsyncClient(
                    base_url=base, auth=auth, timeout=httpx.Timeout(3, connect=2),
                    follow_redirects=False, trust_env=False,
                    limits=httpx.Limits(max_connections=1),
                ) as client:
                    operations = [
                        ("/api/location/setlocationfields", {
                            "longitude": checked["longitude"], "latitude": checked["latitude"],
                            "altitude": checked["altitude"], "planet": "Earth",
                            "name": "Wealth Command Center",
                        }),
                        ("/api/main/time", {"time": checked["julian_day_utc"], "timerate": 0}),
                        ("/api/main/focus", {"target": body, "mode": "center"}),
                    ]
                    for path, form in operations:
                        result = await client.post(path, data=form)
                        result.raise_for_status()
                        if result.text.strip().lower().startswith("error"):
                            raise ValueError("Viewer rejected operation")
                    result = await client.get("/api/main/status")
                    result.raise_for_status()
                    status = result.json()
                    jd = float(status["time"]["jday"])
                    location = status["location"]
                    # In-memory movement is immediate for these APIs. Confirm state,
                    # not merely HTTP success; do not import viewer ephemerides.
                    if not math.isfinite(jd) or abs(jd - checked["julian_day_utc"]) > 1e-6:
                        raise ValueError("Viewer time differs")
                    for field in ("latitude", "longitude", "altitude"):
                        value = float(location[field])
                        if not math.isfinite(value) or abs(value - checked[field]) > 1e-4:
                            raise ValueError("Viewer location differs")
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
        raise StellariumUnavailable(
            "Stellarium synchronization could not be confirmed. Check the local RemoteControl "
            "plugin and its password. The viewer may already have changed partially."
        ) from None
    return {
        "status": "synced", "body": body, "utc": checked["utc"],
        "verified": ["time", "location"],
        "warnings": ["The selection request was accepted; rendered pixels were not verified. "
                     "Stellarium is a viewer, not the source of the symbolic score."],
    }
