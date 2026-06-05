from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import urllib.parse


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "open_event_kit.db"
SESSION_COOKIE = "oek_session"


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS event_state (
            user_id INTEGER PRIMARY KEY,
            checks TEXT NOT NULL DEFAULT '{}',
            profile TEXT NOT NULL DEFAULT '{}',
            plan TEXT NOT NULL DEFAULT '{}',
            runbook TEXT NOT NULL DEFAULT '{}',
            events TEXT NOT NULL DEFAULT '[]',
            selected_event_id TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(event_state)").fetchall()}
    if "runbook" not in columns:
        connection.execute("ALTER TABLE event_state ADD COLUMN runbook TEXT NOT NULL DEFAULT '{}'")
    if "events" not in columns:
        connection.execute("ALTER TABLE event_state ADD COLUMN events TEXT NOT NULL DEFAULT '[]'")
    if "selected_event_id" not in columns:
        connection.execute("ALTER TABLE event_state ADD COLUMN selected_event_id TEXT")
    connection.commit()
    return connection


def hash_password(password, salt=None):
    raw_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, 200_000)
    return (
        base64.b64encode(digest).decode("ascii"),
        base64.b64encode(raw_salt).decode("ascii"),
    )


def verify_password(password, stored_hash, stored_salt):
    digest, _ = hash_password(password, base64.b64decode(stored_salt))
    return secrets.compare_digest(digest, stored_hash)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def read_json(self):
        length = int(self.headers.get("content-length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def write_json(self, data, status=200, extra_headers=None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def get_session_token(self):
        header = self.headers.get("Cookie")
        if not header:
            return None
        jar = cookies.SimpleCookie(header)
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def current_user(self, connection):
        token = self.get_session_token()
        if not token:
            return None
        return connection.execute(
            """
            SELECT users.id, users.name, users.email
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()

    def user_state(self, connection, user_id):
        connection.execute(
            "INSERT OR IGNORE INTO event_state (user_id) VALUES (?)",
            (user_id,),
        )
        connection.commit()
        row = connection.execute(
            "SELECT checks, profile, plan, runbook, events, selected_event_id FROM event_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        events = json.loads(row["events"] or "[]")
        if events:
            return {
                "events": events,
                "selectedEventId": row["selected_event_id"],
            }
        return {
            "checks": json.loads(row["checks"]),
            "profile": json.loads(row["profile"]),
            "plan": json.loads(row["plan"]),
            "runbook": json.loads(row["runbook"]),
        }

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/me":
            with db() as connection:
                user = self.current_user(connection)
                if not user:
                    self.write_json({"user": None, "state": {"checks": {}, "profile": {}, "plan": {}}})
                    return
                self.write_json(
                    {
                        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
                        "state": self.user_state(connection, user["id"]),
                    }
                )
                return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            data = self.read_json()
        except json.JSONDecodeError:
            self.write_json({"error": "Invalid JSON."}, 400)
            return

        if parsed.path == "/api/register":
            name = (data.get("name") or "").strip()
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            if not name or not email or len(password) < 8:
                self.write_json({"error": "Vul naam, e-mail en een wachtwoord van minstens 8 tekens in."}, 400)
                return
            password_hash, salt = hash_password(password)
            token = secrets.token_urlsafe(32)
            try:
                with db() as connection:
                    cursor = connection.execute(
                        "INSERT INTO users (name, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                        (name, email, password_hash, salt),
                    )
                    user_id = cursor.lastrowid
                    connection.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
                    connection.execute("INSERT INTO event_state (user_id) VALUES (?)", (user_id,))
                    connection.commit()
                    self.write_json(
                        {
                            "user": {"id": user_id, "name": name, "email": email},
                            "state": {"events": [], "selectedEventId": None},
                        },
                        extra_headers={"Set-Cookie": f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"},
                    )
            except sqlite3.IntegrityError:
                self.write_json({"error": "Er bestaat al een account met dit e-mailadres."}, 409)
            return

        if parsed.path == "/api/login":
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            with db() as connection:
                user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if not user or not verify_password(password, user["password_hash"], user["salt"]):
                    self.write_json({"error": "E-mail of wachtwoord klopt niet."}, 401)
                    return
                token = secrets.token_urlsafe(32)
                connection.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
                connection.commit()
                self.write_json(
                    {
                        "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
                        "state": self.user_state(connection, user["id"]),
                    },
                    extra_headers={"Set-Cookie": f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"},
                )
            return

        if parsed.path == "/api/logout":
            token = self.get_session_token()
            with db() as connection:
                if token:
                    connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
                    connection.commit()
            self.write_json(
                {"ok": True},
                extra_headers={"Set-Cookie": f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"},
            )
            return

        if parsed.path == "/api/state":
            with db() as connection:
                user = self.current_user(connection)
                if not user:
                    self.write_json({"error": "Log eerst in om je event te bewaren."}, 401)
                    return
                connection.execute(
                    """
                    INSERT INTO event_state (user_id, checks, profile, plan, runbook, events, selected_event_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        checks = excluded.checks,
                        profile = excluded.profile,
                        plan = excluded.plan,
                        runbook = excluded.runbook,
                        events = excluded.events,
                        selected_event_id = excluded.selected_event_id,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        user["id"],
                        json.dumps(data.get("checks") or {}),
                        json.dumps(data.get("profile") or {}),
                        json.dumps(data.get("plan") or {}),
                        json.dumps(data.get("runbook") or {}),
                        json.dumps(data.get("events") or []),
                        data.get("selectedEventId"),
                    ),
                )
                connection.commit()
                self.write_json({"ok": True})
            return

        self.write_json({"error": "Unknown endpoint."}, 404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8001), Handler)
    print("Open Event Kit server running at http://127.0.0.1:8001/index.html")
    server.serve_forever()
