"""Viewer password verifier and persistent sessions on the VPS."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

CREDENTIALS = Path("/etc/pokerfate-live/viewer.json")
SESSIONS = Path("/var/lib/pokerfate-live-sessions/sessions.sqlite3")
COOKIE = "__Host-pf_live"
REMEMBER_SECONDS = 90 * 86400
SESSION_SECONDS = 12 * 3600


def password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)


def credentials_for(password: str, path: Path) -> dict:
    # Preserve the verifier across ordinary releases so remembered devices survive.
    if path.exists():
        record = json.loads(path.read_text())
        if hmac.compare_digest(password_hash(password, bytes.fromhex(record["salt"])).hex(), record["hash"]):
            return record
    salt = secrets.token_bytes(16)
    return {"salt": salt.hex(), "hash": password_hash(password, salt).hex()}


class ViewerAuth:
    def __init__(self, credentials: Path, sessions: Path):
        record = json.loads(credentials.read_text())
        self.salt = bytes.fromhex(record["salt"])
        self.verifier = bytes.fromhex(record["hash"])
        if len(self.salt) != 16 or len(self.verifier) != 32:
            raise ValueError("invalid viewer credentials file")
        self.sessions = sessions
        with closing(sqlite3.connect(self.sessions)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (id BLOB PRIMARY KEY, expires INTEGER NOT NULL)")
            db.execute("DELETE FROM sessions WHERE expires <= ?", (int(time.time()),))

    def authenticate(self, username: str, password: str) -> bool:
        return username == "viewer" and hmac.compare_digest(password_hash(password, self.salt), self.verifier)

    def api_credentials_valid(self, authorization: str) -> bool:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            username, _, password = base64.b64decode(value, validate=True).decode().partition(":")
        except (UnicodeError, ValueError, binascii.Error):
            return False
        return self.authenticate(username, password)

    def _id(self, token: str) -> bytes:
        # Binding sessions to the password verifier also revokes them on rotation.
        return hmac.digest(self.verifier, token.encode(), "sha256")

    def issue(self, remember: bool) -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        ttl = REMEMBER_SECONDS if remember else SESSION_SECONDS
        with closing(sqlite3.connect(self.sessions)) as db, db:
            db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
            db.execute("INSERT INTO sessions VALUES (?, ?)", (self._id(token), now + ttl))
        return token

    def valid(self, token: str) -> bool:
        if len(token) != 43:
            return False
        with closing(sqlite3.connect(self.sessions)) as db:
            return db.execute("SELECT 1 FROM sessions WHERE id = ? AND expires > ?",
                              (self._id(token), int(time.time()))).fetchone() is not None

    def revoke(self, token: str):
        if len(token) == 43:
            with closing(sqlite3.connect(self.sessions)) as db, db:
                db.execute("DELETE FROM sessions WHERE id = ?", (self._id(token),))
