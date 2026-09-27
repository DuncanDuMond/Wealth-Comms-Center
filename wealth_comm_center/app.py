"""Same-origin web/API boundary. No tool has ambient access to another user's data."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from . import __version__
from .equation import PersonalEquation, evaluate
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
COOKIE = "wealth_session"


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def password_ok(password: str, encoded: str) -> bool:
    try:
        _, salt, _ = encoded.split("$")
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except (ValueError, TypeError):
        return False


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value.casefold()


class ProfileInput(Model):
    name: str = Field(min_length=1, max_length=100)
    birth_date: str
    birth_time: str | None = None
    timezone: str = Field(max_length=100)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    place_name: str = Field(default="", max_length=200)
    enneagram_type: str | None = Field(default=None, max_length=20)
    mbti_type: str | None = Field(default=None, max_length=10)
    numerology_name: str | None = Field(default=None, max_length=200)

    @field_validator("birth_date")
    @classmethod
    def date_valid(cls, value):
        parsed = date.fromisoformat(value)
        if not 1800 <= parsed.year <= 2399:
            raise ValueError("Supported birth dates are 1800–2399")
        return parsed.isoformat()

    @field_validator("birth_time")
    @classmethod
    def time_valid(cls, value):
        if not value:
            return None
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", value):
            raise ValueError("Time must be HH:MM or HH:MM:SS")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Select a valid IANA timezone, for example Asia/Tokyo")
        return value


class JournalInput(Model):
    profile_id: str
    kind: Literal["reflection", "decision", "experiment", "location"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=10000)
    outcome: str = Field(default="", max_length=5000)


class AgentInput(Model):
    profile_id: str
    message: str = Field(min_length=1, max_length=4000)
    locale: Literal["en", "ja", "zh-CN", "th", "ko", "vi"] = "en"
    use_cloud_ai: bool = False
    report_date: str | None = None


class StellariumInput(Model):
    profile_id: str
    body: str = Field(default="Jupiter", max_length=30)


class RateLimiter:
    def __init__(self):
        self.events = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key, limit, window=60):
        with self.lock:
            current = time.monotonic()
            if len(self.events) > 10000:
                self.events = defaultdict(deque, {k:v for k,v in self.events.items() if v and v[-1] > current-3600})
            events = self.events[key]
            while events and events[0] <= current-window:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(429, "Too many requests. Please try again shortly.", headers={"Retry-After": str(window)})
            events.append(current)


def create_app(db_path: str | Path | None = None):
    app = FastAPI(title="Wealth Command Center API", version=__version__, docs_url=None, redoc_url=None)
    store = Store(db_path or os.getenv("WEALTH_DB", str(ROOT / "data" / "wealth.db")))
    limiter = RateLimiter()
    app.state.store = store
    secure = os.getenv("WEALTH_SECURE_COOKIES", "false").lower() == "true"

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("X-Wealth-Request") != "1":
                return JSONResponse({"detail": "Missing same-origin request header"}, status_code=403)
            origin = request.headers.get("origin")
            expected = os.getenv("WEALTH_PUBLIC_ORIGIN") or str(request.base_url).rstrip("/")
            if origin and origin != expected:
                return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
            try:
                if int(request.headers.get("content-length", "0")) > 65536:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid content length"}, status_code=400)
            # Enforce the limit even when a client omits Content-Length.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default error includes the submitted input, possibly a password.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    def current_user(request: Request):
        user = store.session(request.cookies.get(COOKIE))
        if not user:
            raise HTTPException(401, "Please sign in")
        return user

    def owned_profile(user, profile_id):
        profile = store.profile(user["id"], profile_id)
        if not profile:
            raise HTTPException(404, "Profile not found")
        return profile

    def session_response(user, response):
        response.set_cookie(COOKIE, store.new_session(user["id"]), httponly=True,
            secure=secure, samesite="strict", max_age=86400*7, path="/")
        return {"user": user}

    @app.get("/api/session")
    def session(request: Request):
        return {"user": store.session(request.cookies.get(COOKIE)), "version": __version__,
            "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "integrations": {"stellarium": os.getenv("STELLARIUM_ENABLED", "false").lower() == "true", "web_sky": False}}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.post("/api/auth/register", status_code=201)
    def register(data: Credentials, request: Request, response: Response):
        limiter.check(("auth", request.client.host), 12, 300)
        if os.getenv("WEALTH_REGISTRATION", "true").lower() != "true":
            raise HTTPException(403, "Registration is currently closed")
        try:
            user = store.register(data.email, password_hash(data.password))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Unable to register this email. Try signing in.")
        store.audit(user["id"], "account.created")
        return session_response(user, response)

    @app.post("/api/auth/login")
    def login(data: Credentials, request: Request, response: Response):
        limiter.check(("auth", request.client.host), 12, 300)
        limiter.check(("email", data.email), 12, 300)
        user = store.credentials(data.email)
        # Equal-cost hash for an unknown email prevents a cheap timing oracle.
        encoded = user["password"] if user else password_hash("not-a-real-password", "0"*32)
        if not password_ok(data.password, encoded) or not user:
            raise HTTPException(401, "Email or password is incorrect")
        store.logout(request.cookies.get(COOKIE))
        store.audit(user["id"], "account.login")
        return session_response({"id": user["id"], "email": user["email"]}, response)

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        store.logout(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/profiles")
    def profiles(user=Depends(current_user)):
        return store.profiles(user["id"])

    @app.get("/api/places")
    def places(q: str = "", user=Depends(current_user)):
        from .places import search_places
        limiter.check(("places", user["id"]), 120)
        return search_places(q)

    @app.post("/api/profiles", status_code=201)
    def add_profile(data: ProfileInput, user=Depends(current_user)):
        if len(store.profiles(user["id"])) >= 100:
            raise HTTPException(409, "This account has reached the 100-profile limit")
        result = store.save_profile(user["id"], data.model_dump())
        store.audit(user["id"], "profile.created", result["id"])
        return result

    @app.patch("/api/profiles/{profile_id}")
    def edit_profile(profile_id: str, data: ProfileInput, user=Depends(current_user)):
        owned_profile(user, profile_id)
        result = store.save_profile(user["id"], data.model_dump(), profile_id)
        store.audit(user["id"], "profile.updated", profile_id)
        return result

    @app.delete("/api/profiles/{profile_id}")
    def delete_profile(profile_id: str, user=Depends(current_user)):
        owned_profile(user, profile_id)
        store.delete_profile(user["id"], profile_id)
        store.audit(user["id"], "profile.deleted", profile_id)
        return {"ok": True}

    async def calculate(user, profile_id, operation, selected_date=None):
        profile = owned_profile(user, profile_id)
        limiter.check(("compute", user["id"]), 60)
        from . import engine
        try:
            if operation == "report":
                if selected_date:
                    date.fromisoformat(selected_date)
                result = await run_in_threadpool(engine.build_report, profile, selected_date)
            else:
                result = await run_in_threadpool(getattr(engine, f"build_{operation}"), profile)
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.get("/api/profiles/{profile_id}/report")
    async def report(profile_id: str, date: str | None = None, user=Depends(current_user)):
        return await calculate(user, profile_id, "report", date)

    @app.get("/api/profiles/{profile_id}/map")
    async def map_data(profile_id: str, user=Depends(current_user)):
        return await calculate(user, profile_id, "map")

    @app.get("/api/profiles/{profile_id}/sky-state")
    async def sky_state(profile_id: str, user=Depends(current_user)):
        return await calculate(user, profile_id, "sky_state")

    @app.get("/api/profiles/{profile_id}/cards/{entity}")
    async def cosmic_card(profile_id: str, entity: str, format: Literal["json", "svg"] = "json",
                         locale: Literal["en", "ja", "zh-CN", "th", "ko", "vi"] = "en",
                         user=Depends(current_user)):
        result = await calculate(user, profile_id, "report")
        from .cosmic_cards import resolve_card, render_svg
        try:
            card = resolve_card(result, entity, locale)
            if format == "svg":
                return Response(render_svg(card), media_type="image/svg+xml",
                    headers={"Content-Disposition": f'inline; filename="cosmic-{entity}.svg"'})
            return card
        except (KeyError, ValueError) as exc:
            raise HTTPException(422, str(exc))

    @app.get("/api/frameworks/nakshatra")
    def nakshatra_status(user=Depends(current_user)):
        from .boundaries import boundary_status
        return boundary_status()

    @app.post("/api/equation")
    async def personal_equation(data: PersonalEquation, user=Depends(current_user)):
        import json
        report_data = await calculate(user, data.profile_id, "report")
        result = evaluate(data, report_data["score"]["value"])
        result["baseline_provenance"] = report_data["provenance"]
        if data.save:
            entry = store.add_journal(user["id"], {"profile_id": data.profile_id, "kind": "experiment",
                "title": "Personal equation experiment", "body": json.dumps(result, ensure_ascii=False), "outcome": ""})
            result["journal_id"] = entry["id"]
            store.audit(user["id"], "equation.saved", entry["id"])
        return result

    @app.get("/api/profiles/{profile_id}/stellarium-script")
    async def stellarium_script(profile_id: str, body: str = "Jupiter", user=Depends(current_user)):
        from .stellarium import make_script
        state = await calculate(user, profile_id, "sky_state")
        try:
            script = make_script(state, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        store.audit(user["id"], "stellarium.script_exported", profile_id)
        return Response(script, media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="wealth-sky.ssc"'})

    @app.post("/api/integrations/stellarium")
    async def stellarium_connect(data: StellariumInput, user=Depends(current_user)):
        from .stellarium import send_to_stellarium
        if os.getenv("STELLARIUM_ENABLED", "false").lower() != "true":
            raise HTTPException(403, "Live Stellarium control is disabled. Use the script download, or explicitly enable local control on a private server.")
        state = await calculate(user, data.profile_id, "sky_state")
        try:
            result = await send_to_stellarium(state, data.body)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except Exception:
            raise HTTPException(503, "Stellarium is unavailable. Check the local RemoteControl plugin settings.")
        store.audit(user["id"], "stellarium.focused", data.profile_id)
        return result

    @app.post("/api/agent")
    async def agent(data: AgentInput, user=Depends(current_user)):
        limiter.check(("agent", user["id"]), 10)
        from .agent import respond
        report_data = await calculate(user, data.profile_id, "report", data.report_date)
        result = await run_in_threadpool(respond, data.message, data.locale, report_data,
            allow_cloud=data.use_cloud_ai)
        store.audit(user["id"], "agent.cloud_response" if result.get("mode") == "anthropic" else "agent.local_response", data.profile_id)
        return result

    @app.get("/api/journal")
    def journal(profile_id: str | None = None, user=Depends(current_user)):
        if profile_id:
            owned_profile(user, profile_id)
        return store.journal(user["id"], profile_id)

    @app.post("/api/journal", status_code=201)
    def add_journal(data: JournalInput, user=Depends(current_user)):
        owned_profile(user, data.profile_id)
        result = store.add_journal(user["id"], data.model_dump())
        if not result:
            raise HTTPException(404, "Profile not found")
        store.audit(user["id"], "journal.created", result["id"])
        return result

    @app.delete("/api/journal/{entry_id}")
    def delete_journal(entry_id: str, user=Depends(current_user)):
        if not store.delete_journal(user["id"], entry_id):
            raise HTTPException(404, "Entry not found")
        store.audit(user["id"], "journal.deleted", entry_id)
        return {"ok": True}

    @app.get("/api/audit")
    def audit(user=Depends(current_user)):
        return store.audits(user["id"])

    @app.get("/api/export")
    def export(user=Depends(current_user)):
        return JSONResponse({"version": __version__, "user": user, "profiles": store.profiles(user["id"]),
            "journal": store.journal(user["id"]), "audit": store.audits(user["id"])},
            headers={"Content-Disposition": 'attachment; filename="wealth-command-center-data.json"'})

    @app.delete("/api/account")
    def delete_account(data: Credentials, response: Response, user=Depends(current_user)):
        credentials = store.credentials(user["email"])
        if data.email != user["email"] or not password_ok(data.password, credentials["password"]):
            raise HTTPException(401, "Email or password is incorrect")
        store.delete_user(user["id"])
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    web = ROOT / "web"
    web.mkdir(exist_ok=True)
    app.mount("/assets", StaticFiles(directory=web), name="assets")

    @app.get("/")
    def index():
        return FileResponse(web / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/sw.js")
    def service_worker():
        return FileResponse(web / "sw.js", media_type="application/javascript",
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

    return app


app = create_app()
