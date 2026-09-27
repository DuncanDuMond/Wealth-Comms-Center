import asyncio
import math
from urllib.parse import parse_qs

import httpx
import pytest

from wealth_command_center import stellarium


STATE = {
    "schema_version": "1.0",
    "utc": "2000-01-01T12:00:00Z",
    "julian_day_utc": 2451545.0,
    "latitude": 35.68,
    "longitude": 139.76,
    "altitude": 12,
    "source": "python/swisseph",
}


def test_script_exports_utc_degrees_and_freezes_time():
    result = stellarium.make_script(STATE, "Jupiter")
    assert 'core.setDate("2000-01-01T12:00:00", "utc", false);' in result
    assert "core.setObserverLocation(139.76, 35.68, 12.0, 0" in result
    assert "core.setTimeRate(0);" in result
    assert 'core.selectObjectByName("Jupiter", true);' in result
    assert "2451545.0" in result


@pytest.mark.parametrize("body", ['Jupiter");evil();', "Selena", "Lot of Fortune", "Earth"])
def test_nonphysical_and_injected_objects_rejected(body):
    with pytest.raises(ValueError):
        stellarium.make_script(STATE, body)


@pytest.mark.parametrize(
    "field,value",
    [("latitude", 91), ("longitude", -181), ("altitude", math.nan),
     ("julian_day_utc", math.inf), ("utc", "2000-01-01T12:00:00"),
     ("utc", '2000-01-01");evil()'), ("latitude", True)],
)
def test_invalid_state_rejected(field, value):
    with pytest.raises(ValueError):
        stellarium.make_script({**STATE, field: value})


@pytest.mark.parametrize("url", [
    "https://example.com", "http://127.0.0.1.evil.test:8090", "http://169.254.169.254",
    "http://user:password@127.0.0.1:8090", "http://127.0.0.1/api", "file:///etc/passwd",
    "http://127.0.0.1:8090?redirect=x", "http://127.0.0.2:8090", "http://[::1]:0",
])
def test_remote_or_ambiguous_config_rejected(monkeypatch, url):
    monkeypatch.setenv("STELLARIUM_ENABLED", "true")
    monkeypatch.setenv("STELLARIUM_URL", url)
    with pytest.raises(ValueError):
        asyncio.run(stellarium.send_to_stellarium(STATE))


def test_desktop_disabled_by_default(monkeypatch):
    monkeypatch.delenv("STELLARIUM_ENABLED", raising=False)
    assert not stellarium.stellarium_enabled()
    with pytest.raises(stellarium.StellariumUnavailable):
        asyncio.run(stellarium.send_to_stellarium(STATE))


def test_sync_uses_authoritative_jd_and_expected_http_contract(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "time": {"jday": 2451545.0},
                "location": {"latitude": 35.68, "longitude": 139.76, "altitude": 12},
            })
        return httpx.Response(200, text="ok")

    original = httpx.AsyncClient
    monkeypatch.setattr(stellarium.httpx, "AsyncClient", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handler)
    ))
    monkeypatch.setenv("STELLARIUM_ENABLED", "true")
    monkeypatch.setenv("STELLARIUM_URL", "http://localhost:8090")
    monkeypatch.setenv("STELLARIUM_PASSWORD", "secret")
    result = asyncio.run(stellarium.send_to_stellarium(STATE, "Jupiter"))
    assert result["status"] == "synced"
    assert [r.url.path for r in requests] == [
        "/api/location/setlocationfields", "/api/main/time", "/api/main/focus", "/api/main/status"
    ]
    assert all(r.url.host == "127.0.0.1" for r in requests)
    assert parse_qs(requests[1].content.decode()) == {"time": ["2451545.0"], "timerate": ["0"]}
    assert parse_qs(requests[2].content.decode()) == {"target": ["Jupiter"], "mode": ["center"]}
    assert requests[0].headers["authorization"].startswith("Basic ")
    assert "secret" not in str(result)


def test_redirect_is_not_followed_and_failure_sanitized(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://external.test/password-secret"})
    original = httpx.AsyncClient
    monkeypatch.setattr(stellarium.httpx, "AsyncClient", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handler)
    ))
    monkeypatch.setenv("STELLARIUM_ENABLED", "true")
    monkeypatch.setenv("STELLARIUM_URL", "http://127.0.0.1:8090")
    with pytest.raises(stellarium.StellariumUnavailable) as failure:
        asyncio.run(stellarium.send_to_stellarium(STATE))
    assert len(seen) == 1
    assert "password-secret" not in str(failure.value)


def test_stale_view_is_not_reported_as_synced(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"time": {"jday": 1}, "location": {}})
    original = httpx.AsyncClient
    monkeypatch.setattr(stellarium.httpx, "AsyncClient", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handler)
    ))
    monkeypatch.setenv("STELLARIUM_ENABLED", "true")
    monkeypatch.setenv("STELLARIUM_URL", "http://127.0.0.1:8090")
    with pytest.raises(stellarium.StellariumUnavailable):
        asyncio.run(stellarium.send_to_stellarium(STATE))
