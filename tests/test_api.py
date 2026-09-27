from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from wealth_command_center.app import create_app

HEADERS = {"X-Wealth-Request": "1"}
PROFILE = {"name": "Test person", "birth_date": "1990-06-15", "birth_time": "10:30",
           "timezone": "Asia/Tokyo", "latitude": 35.68, "longitude": 139.69, "place_name": "Tokyo"}


@pytest.fixture
def application(tmp_path):
    return create_app(tmp_path / "test.db")


def account(application, email="one@example.test"):
    client = TestClient(application)
    response = client.post("/api/auth/register", json={"email": email, "password": "test-password-long-123"}, headers=HEADERS)
    assert response.status_code == 201, response.text
    return client


def test_private_by_default(application):
    client = TestClient(application)
    assert client.get("/api/session").json()["user"] is None
    for route in ("/api/profiles", "/api/journal", "/api/export", "/api/audit"):
        response = client.get(route)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "private, no-store"


def test_sessions_and_security_headers(application):
    client = account(application)
    assert client.get("/api/session").json()["user"]["email"] == "one@example.test"
    cookie = client.cookies["wealth_session"]
    with application.state.store.connect() as db:
        row = db.execute("SELECT token_hash FROM sessions").fetchone()
        assert row[0] != cookie and len(row[0]) == 64
        password = db.execute("SELECT password FROM users").fetchone()[0]
        assert password.startswith("scrypt$")
    response = client.get("/api/profiles")
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.post("/api/auth/logout", json={}, headers=HEADERS).status_code == 200
    assert client.get("/api/profiles").status_code == 401
    assert TestClient(application).get("/api/profiles", cookies={"wealth_session": cookie}).status_code == 401


def test_user_isolation_and_cascade(application):
    first = account(application)
    second = account(application, "two@example.test")
    profile = first.post("/api/profiles", json=PROFILE, headers=HEADERS).json()
    pid = profile["id"]
    assert second.get("/api/profiles").json() == []
    for suffix in ("report", "map", "sky-state", "stellarium-script", "cards/sun"):
        assert second.get(f"/api/profiles/{pid}/{suffix}").status_code == 404
    assert second.delete(f"/api/profiles/{pid}", headers=HEADERS).status_code == 404
    assert second.patch(f"/api/profiles/{pid}", json=PROFILE, headers=HEADERS).status_code == 404
    entry = {"profile_id": pid, "kind": "experiment", "title": "Check assumption", "body": "Observe outcomes", "outcome": ""}
    assert second.post("/api/journal", json=entry, headers=HEADERS).status_code == 404
    saved = first.post("/api/journal", json=entry, headers=HEADERS).json()
    assert second.delete(f"/api/journal/{saved['id']}", headers=HEADERS).status_code == 404
    assert first.get("/api/export").json()["journal"][0]["id"] == saved["id"]
    assert len(first.get("/api/audit").json()) >= 3
    assert first.delete(f"/api/profiles/{pid}", headers=HEADERS).status_code == 200
    assert first.get("/api/journal").json() == []


def test_csrf_and_payload_limits(application):
    client = account(application)
    assert client.post("/api/profiles", json=PROFILE).status_code == 403
    assert client.post("/api/profiles", json=PROFILE, headers={**HEADERS, "Origin": "https://evil.test"}).status_code == 403
    assert client.post("/api/profiles", json=PROFILE, headers={**HEADERS, "Origin": "http://testserver"}).status_code == 201
    assert client.post("/api/profiles", content="x" * 70000, headers=HEADERS).status_code == 413


@pytest.mark.parametrize("changes", [{"latitude": 91}, {"longitude": -181}, {"timezone": "made/up"},
                                      {"birth_time": "25:31"}, {"birth_date": "2021-02-29"}, {"name": ""}])
def test_profile_validation(application, changes):
    client = account(application)
    response = client.post("/api/profiles", json={**PROFILE, **changes}, headers=HEADERS)
    assert response.status_code == 422
    assert client.get("/api/profiles").json() == []


def test_password_input_not_echoed(application):
    client = TestClient(application)
    response = client.post("/api/auth/register", json={"email": "invalid", "password": "SECRET"}, headers=HEADERS)
    assert response.status_code == 422
    assert "SECRET" not in response.text


def test_unknown_birth_time_saved_but_not_calculated(application):
    client = account(application)
    profile = client.post("/api/profiles", json={**PROFILE, "birth_time": None}, headers=HEADERS).json()
    for operation in ("report", "map", "sky-state"):
        response = client.get(f"/api/profiles/{profile['id']}/{operation}")
        assert response.status_code == 422, response.text
        assert "unknown" in response.json()["detail"].lower()
    corrected = client.patch(f"/api/profiles/{profile['id']}", json=PROFILE, headers=HEADERS)
    assert corrected.status_code == 200


def test_unicode_profiles_and_restart(tmp_path):
    path = tmp_path / "persistent.db"
    first_app = create_app(path)
    client = account(first_app)
    name = "太陽 • 中文 • ภาษาไทย • 한국어 • Tiếng Việt"
    profile = client.post("/api/profiles", json={**PROFILE, "name": name}, headers=HEADERS).json()
    next_client = TestClient(create_app(path))
    next_client.cookies.update(client.cookies)
    assert next_client.get("/api/profiles").json()[0]["name"] == name
    assert next_client.get("/api/profiles").json()[0]["id"] == profile["id"]


def test_account_deletion_requires_credentials(application):
    client = account(application)
    client.post("/api/profiles", json=PROFILE, headers=HEADERS)
    bad = {"email": "one@example.test", "password": "wrong-password-long"}
    assert client.request("DELETE", "/api/account", json=bad, headers=HEADERS).status_code == 401
    good = {**bad, "password": "test-password-long-123"}
    assert client.request("DELETE", "/api/account", json=good, headers=HEADERS).status_code == 200
    with application.state.store.connect() as db:
        for table in ("users", "sessions", "profiles", "journal", "audit"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_duplicate_signup_and_login_failure(application):
    account(application)
    client = TestClient(application)
    credentials = {"email": "one@example.test", "password": "test-password-long-123"}
    assert client.post("/api/auth/register", json=credentials, headers=HEADERS).status_code == 409
    assert client.post("/api/auth/login", json={**credentials, "password": "bad-password-long"}, headers=HEADERS).status_code == 401
    assert client.post("/api/auth/login", json=credentials, headers=HEADERS).status_code == 200


def test_parallel_private_writes(application):
    client = account(application)
    owner = client.get("/api/session").json()["user"]["id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(lambda i: application.state.store.save_profile(owner, {**PROFILE, "name": str(i)}), range(12)))
    assert len({v["id"] for v in values}) == 12
    assert len(client.get("/api/profiles").json()) == 12


def test_cloud_ai_opt_in_boundary(application, monkeypatch):
    from wealth_command_center import agent, engine
    client = account(application)
    profile = client.post("/api/profiles", json=PROFILE, headers=HEADERS).json()
    calls = []
    dates = []
    def make_report(*args):
        dates.append(args[1])
        return {"score": {"value": 25}, "evidence": []}
    monkeypatch.setattr(engine, "build_report", make_report)
    def response(*args, **kwargs):
        calls.append(kwargs["allow_cloud"])
        return {"answer": "Test", "mode": "deterministic", "evidence": [], "tool_trace": [], "warnings": []}
    monkeypatch.setattr(agent, "respond", response)
    base = {"profile_id": profile["id"], "message": "Explain", "locale": "ja", "report_date": "2026-05-01"}
    assert client.post("/api/agent", json=base, headers=HEADERS).status_code == 200
    assert client.post("/api/agent", json={**base, "use_cloud_ai": True}, headers=HEADERS).status_code == 200
    assert calls == [False, True]
    assert dates == ["2026-05-01", "2026-05-01"]


def test_password_whitespace_preserved(application):
    client = TestClient(application)
    credentials = {"email": "whitespace@example.test", "password": "  exact-password-value  "}
    assert client.post("/api/auth/register", json=credentials, headers=HEADERS).status_code == 201
    client.post("/api/auth/logout", json={}, headers=HEADERS)
    assert client.post("/api/auth/login", json={**credentials, "password": credentials["password"].strip()}, headers=HEADERS).status_code == 401
    assert client.post("/api/auth/login", json=credentials, headers=HEADERS).status_code == 200


def test_real_equation_card_and_boundary_routes(application):
    client = account(application)
    profile = client.post("/api/profiles", json=PROFILE, headers=HEADERS).json()
    result = client.post("/api/equation", json={"profile_id": profile["id"], "capital": 30, "save": True}, headers=HEADERS)
    assert result.status_code == 200, result.text
    assert result.json()["kind"] == "experimental"
    assert result.json()["journal_id"]
    assert client.get("/api/journal").json()[0]["kind"] == "experiment"
    card = client.get(f"/api/profiles/{profile['id']}/cards/sun?locale=ko")
    assert card.status_code == 200, card.text
    svg = client.get(f"/api/profiles/{profile['id']}/cards/sun?locale=vi&format=svg")
    assert svg.status_code == 200
    assert "image/svg+xml" in svg.headers["content-type"]
    assert "<svg" in svg.text
    assert client.get("/api/frameworks/nakshatra").status_code == 200
    assert client.get("/api/places?q=Tokyo").json()[0]["timezone"] == "Asia/Tokyo"
