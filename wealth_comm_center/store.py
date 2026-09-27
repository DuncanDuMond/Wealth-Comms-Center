"""Small transactional SQLite store. Every user-owned query includes owner_id."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    document TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS profiles_owner ON profiles(owner_id);
                CREATE TABLE IF NOT EXISTS journal (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
                    outcome TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS journal_owner ON journal(owner_id, profile_id);
                CREATE TABLE IF NOT EXISTS audit (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    action TEXT NOT NULL, target_id TEXT, created_at TEXT NOT NULL);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def register(self, email, password_hash):
        user = {"id": str(uuid.uuid4()), "email": email}
        with self.connect() as db:
            db.execute("INSERT INTO users VALUES (?,?,?,?)", (user["id"], email, password_hash, now()))
        return user

    def credentials(self, email):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            return dict(row) if row else None

    def new_session(self, owner):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (self.token_hash(token), owner, time.time()+86400*7))
        return token

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session(self, token):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute("""SELECT users.id, users.email FROM sessions
                JOIN users ON users.id=sessions.owner_id WHERE token_hash=? AND expires>?""",
                (self.token_hash(token), time.time())).fetchone()
            return dict(row) if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (self.token_hash(token or ""),))

    def profiles(self, owner):
        with self.connect() as db:
            return [self.decode_profile(row) for row in db.execute(
                "SELECT * FROM profiles WHERE owner_id=? ORDER BY created_at", (owner,))]

    @staticmethod
    def decode_profile(row):
        return {**json.loads(row["document"]), "id": row["id"], "created_at": row["created_at"]}

    def profile(self, owner, profile_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM profiles WHERE owner_id=? AND id=?", (owner, profile_id)).fetchone()
            return self.decode_profile(row) if row else None

    def save_profile(self, owner, document, profile_id=None):
        with self.connect() as db:
            if profile_id:
                changed = db.execute("UPDATE profiles SET document=? WHERE id=? AND owner_id=?",
                    (json.dumps(document, ensure_ascii=False), profile_id, owner)).rowcount
                if not changed:
                    return None
            else:
                profile_id = str(uuid.uuid4())
                db.execute("INSERT INTO profiles VALUES (?,?,?,?)",
                    (profile_id, owner, json.dumps(document, ensure_ascii=False), now()))
        return self.profile(owner, profile_id)

    def delete_profile(self, owner, profile_id):
        with self.connect() as db:
            return db.execute("DELETE FROM profiles WHERE id=? AND owner_id=?", (profile_id, owner)).rowcount

    def journal(self, owner, profile_id=None):
        with self.connect() as db:
            rows = db.execute("""SELECT id,profile_id,kind,title,body,outcome,created_at FROM journal
                WHERE owner_id=? AND (? IS NULL OR profile_id=?) ORDER BY created_at DESC""",
                (owner, profile_id, profile_id))
            return [dict(row) for row in rows]

    def add_journal(self, owner, entry):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM profiles WHERE id=? AND owner_id=?",
                (entry["profile_id"], owner)).fetchone():
                return None
            saved = {"id": str(uuid.uuid4()), **entry, "created_at": now()}
            db.execute("INSERT INTO journal VALUES (?,?,?,?,?,?,?,?)", (saved["id"], owner,
                saved["profile_id"], saved["kind"], saved["title"], saved["body"], saved["outcome"], saved["created_at"]))
            return saved

    def delete_journal(self, owner, entry_id):
        with self.connect() as db:
            return db.execute("DELETE FROM journal WHERE id=? AND owner_id=?", (entry_id, owner)).rowcount

    def audit(self, owner, action, target=None):
        with self.connect() as db:
            db.execute("INSERT INTO audit VALUES (?,?,?,?,?)", (str(uuid.uuid4()), owner, action, target, now()))

    def audits(self, owner):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,action,target_id,created_at FROM audit WHERE owner_id=? ORDER BY created_at DESC LIMIT 200", (owner,))]

    def delete_user(self, owner):
        with self.connect() as db:
            db.execute("DELETE FROM users WHERE id=?", (owner,))

