"""SQLite data layer (sync sqlite3, wrapped via asyncio.to_thread when needed)."""
from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from typing import Iterable, Optional

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT NOT NULL,
    role TEXT,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    segment TEXT DEFAULT 'pre_webinar',
    unsubscribed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta TEXT,
    FOREIGN KEY (user_id) REFERENCES users(tg_id)
);

CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_users_segment ON users(segment, unsubscribed);
"""

VALID_SEGMENTS = {
    "pre_webinar",
    "attended_live",
    "no_show",
    "hot_lead",
    "customer",
    "churned",
}


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


def get_user(tg_id: int) -> Optional[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()


def find_user(identifier: str) -> Optional[sqlite3.Row]:
    """By tg_id (numeric) or @username."""
    with _conn() as c:
        if identifier.lstrip("-").isdigit():
            return c.execute("SELECT * FROM users WHERE tg_id=?", (int(identifier),)).fetchone()
        uname = identifier.lstrip("@")
        return c.execute("SELECT * FROM users WHERE username=?", (uname,)).fetchone()


def upsert_user(tg_id: int, username: Optional[str], name: str, role: Optional[str]) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO users (tg_id, username, name, role, segment, unsubscribed)
            VALUES (?, ?, ?, ?, 'pre_webinar', 0)
            ON CONFLICT(tg_id) DO UPDATE SET
                username=excluded.username,
                name=excluded.name,
                role=excluded.role,
                unsubscribed=0
            """,
            (tg_id, username, name, role),
        )


def log_event(user_id: int, event_type: str, meta: Optional[dict] = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO events (user_id, event_type, meta) VALUES (?, ?, ?)",
            (user_id, event_type, json.dumps(meta) if meta else None),
        )


def set_segment(tg_id: int, segment: str) -> None:
    if segment not in VALID_SEGMENTS:
        raise ValueError(f"Invalid segment: {segment}")
    with _conn() as c:
        c.execute("UPDATE users SET segment=? WHERE tg_id=?", (segment, tg_id))


def set_unsubscribed(tg_id: int, value: int = 1) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET unsubscribed=? WHERE tg_id=?", (value, tg_id))


def get_users_for_broadcast(segments: Iterable[str]) -> list[sqlite3.Row]:
    segs = list(segments)
    if not segs:
        return []
    placeholders = ",".join("?" * len(segs))
    q = f"SELECT * FROM users WHERE unsubscribed=0 AND segment IN ({placeholders})"
    with _conn() as c:
        return c.execute(q, segs).fetchall()


def get_users_not_in_segments(segments: Iterable[str]) -> list[sqlite3.Row]:
    segs = list(segments)
    placeholders = ",".join("?" * len(segs))
    q = f"SELECT * FROM users WHERE unsubscribed=0 AND segment NOT IN ({placeholders})"
    with _conn() as c:
        return c.execute(q, segs).fetchall()


def stats() -> dict:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        unsub = c.execute("SELECT COUNT(*) FROM users WHERE unsubscribed=1").fetchone()[0]
        by_seg = {
            row["segment"]: row["n"]
            for row in c.execute("SELECT segment, COUNT(*) AS n FROM users GROUP BY segment")
        }
    return {"total": total, "unsubscribed": unsub, "by_segment": by_seg}


def export_csv(path: str) -> None:
    import csv
    with _conn() as c, open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tg_id", "username", "name", "role", "registered_at", "segment", "unsubscribed"])
        for r in c.execute("SELECT * FROM users"):
            w.writerow([r["tg_id"], r["username"], r["name"], r["role"],
                        r["registered_at"], r["segment"], r["unsubscribed"]])
