"""SQLite data layer with WAL mode for safe bot + web concurrency.

- Bot side: writes (registration, segment changes, events).
- Web side: reads + segment updates.
- WAL + busy_timeout=5000ms eliminates 'database is locked' under normal load.
"""
from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
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
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_users_segment ON users(segment, unsubscribed);
CREATE INDEX IF NOT EXISTS idx_users_registered ON users(registered_at);
"""

VALID_SEGMENTS = {
    "pre_webinar",
    "attended_live",
    "no_show",
    "hot_lead",
    "customer",
    "churned",
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _conn():
    c = get_conn()
    try:
        yield c
    finally:
        c.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


# ---------- Core ops used by the bot ----------

def get_user(tg_id: int) -> Optional[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()


def find_user(identifier: str) -> Optional[sqlite3.Row]:
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


def users_already_sent(job_id: str) -> set[int]:
    """tg_ids that already received broadcast_<job_id> — used to make scheduled
    broadcasts idempotent so a restart can't re-send to the same people."""
    with _conn() as c:
        rows = c.execute(
            "SELECT DISTINCT user_id FROM events WHERE event_type=?",
            (f"broadcast_{job_id}",),
        ).fetchall()
    return {r[0] for r in rows}


def get_segment_members(segment: str) -> list[sqlite3.Row]:
    """All users in a segment (or everyone if 'all'), INCLUDING unsubscribed.
    The caller decides who to skip — used by /broadcast_doc to count skipped."""
    with _conn() as c:
        if segment == "all":
            return c.execute("SELECT * FROM users").fetchall()
        if segment not in VALID_SEGMENTS:
            raise ValueError(f"Invalid segment: {segment}")
        return c.execute("SELECT * FROM users WHERE segment=?", (segment,)).fetchall()


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


# ---------- Analytics for the web dashboard ----------

def stats_extended() -> dict:
    base = stats()
    with _conn() as c:
        def count_since(delta: timedelta) -> int:
            since = (datetime.utcnow() - delta).strftime("%Y-%m-%d %H:%M:%S")
            return c.execute(
                "SELECT COUNT(*) FROM users WHERE registered_at >= ?", (since,)
            ).fetchone()[0]

        reg_1h = count_since(timedelta(hours=1))
        reg_24h = count_since(timedelta(hours=24))
        reg_7d = count_since(timedelta(days=7))
        since_24h = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        events_24h = c.execute(
            "SELECT COUNT(*) FROM events WHERE created_at >= ?", (since_24h,)
        ).fetchone()[0]

    return {
        "users_total": base["total"],
        "users_active": base["total"] - base["unsubscribed"],
        "users_unsubscribed": base["unsubscribed"],
        "by_segment": base["by_segment"],
        "registered_last_1h": reg_1h,
        "registered_last_24h": reg_24h,
        "registered_last_7d": reg_7d,
        "events_last_24h": events_24h,
    }


def funnel() -> dict:
    with _conn() as c:
        registered = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        attended = c.execute(
            "SELECT COUNT(*) FROM users WHERE segment IN ('attended_live','hot_lead','customer')"
        ).fetchone()[0]
        clicked_program = c.execute(
            """SELECT COUNT(DISTINCT user_id) FROM events
               WHERE event_type IN ('clicked_landing','clicked_call')"""
        ).fetchone()[0]
        hot_lead = c.execute(
            "SELECT COUNT(*) FROM users WHERE segment IN ('hot_lead','customer')"
        ).fetchone()[0]
        customer = c.execute(
            "SELECT COUNT(*) FROM users WHERE segment='customer'"
        ).fetchone()[0]

    raw = [
        ("Registered", registered),
        ("Attended live", attended),
        ("Clicked program", clicked_program),
        ("Hot lead", hot_lead),
        ("Customer", customer),
    ]
    stages = []
    prev = None
    for name, count in raw:
        rate = None if prev in (None, 0) else round(count / prev, 4)
        stages.append({"name": name, "count": count, "rate_from_prev": rate})
        prev = count
    return {"stages": stages}


def timeline(bucket: str = "hour", days: int = 7) -> list[dict]:
    if bucket not in ("hour", "day"):
        raise ValueError("bucket must be 'hour' or 'day'")
    if days not in (1, 7, 30):
        raise ValueError("days must be 1, 7, or 30")
    fmt = "%Y-%m-%dT%H:00:00" if bucket == "hour" else "%Y-%m-%dT00:00:00"
    sqlite_fmt = "%Y-%m-%dT%H:00:00" if bucket == "hour" else "%Y-%m-%dT00:00:00"
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as c:
        regs = {
            row[0]: row[1] for row in c.execute(
                f"SELECT strftime('{sqlite_fmt}', registered_at) AS b, COUNT(*) "
                "FROM users WHERE registered_at >= ? GROUP BY b", (since,)
            )
        }
        evs = {
            row[0]: row[1] for row in c.execute(
                f"SELECT strftime('{sqlite_fmt}', created_at) AS b, COUNT(*) "
                "FROM events WHERE created_at >= ? GROUP BY b", (since,)
            )
        }
    buckets = sorted(set(regs) | set(evs))
    return [{"bucket": b, "registrations": regs.get(b, 0), "events": evs.get(b, 0)} for b in buckets]


def list_users(segment: Optional[str], search: Optional[str],
               limit: int, offset: int) -> tuple[list[dict], int]:
    where = []
    params: list = []
    if segment:
        if segment not in VALID_SEGMENTS:
            raise ValueError(f"Invalid segment: {segment}")
        where.append("u.segment = ?")
        params.append(segment)
    if search:
        where.append("(LOWER(u.username) LIKE ? OR LOWER(u.name) LIKE ?)")
        s = f"%{search.lower()}%"
        params.extend([s, s])
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM users u {where_sql}", params).fetchone()[0]
        rows = c.execute(
            f"""
            SELECT u.*,
                   (SELECT COUNT(*) FROM events e WHERE e.user_id = u.tg_id) AS events_count,
                   (SELECT MAX(created_at) FROM events e WHERE e.user_id = u.tg_id) AS last_event_at
            FROM users u
            {where_sql}
            ORDER BY u.registered_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    return [_user_row_to_dict(r) for r in rows], total


def _user_row_to_dict(r: sqlite3.Row) -> dict:
    return {
        "tg_id": r["tg_id"],
        "username": r["username"],
        "name": r["name"],
        "role": r["role"],
        "segment": r["segment"],
        "unsubscribed": bool(r["unsubscribed"]),
        "registered_at": r["registered_at"],
        "events_count": r["events_count"] if "events_count" in r.keys() else None,
        "last_event_at": r["last_event_at"] if "last_event_at" in r.keys() else None,
    }


def get_user_details(tg_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            """
            SELECT u.*,
                   (SELECT COUNT(*) FROM events e WHERE e.user_id = u.tg_id) AS events_count,
                   (SELECT MAX(created_at) FROM events e WHERE e.user_id = u.tg_id) AS last_event_at
            FROM users u WHERE u.tg_id = ?
            """,
            (tg_id,),
        ).fetchone()
        if not row:
            return None
        events = c.execute(
            "SELECT id, event_type, created_at, meta FROM events WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT 30",
            (tg_id,),
        ).fetchall()
    return {
        "user": _user_row_to_dict(row),
        "events": [
            {"id": e["id"], "event_type": e["event_type"],
             "created_at": e["created_at"], "meta": e["meta"]}
            for e in events
        ],
    }


def list_events(event_type: Optional[str], user_id: Optional[int],
                limit: int, offset: int) -> tuple[list[dict], int, list[str]]:
    where = []
    params: list = []
    if event_type:
        where.append("e.event_type = ?")
        params.append(event_type)
    if user_id is not None:
        where.append("e.user_id = ?")
        params.append(user_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM events e {where_sql}", params).fetchone()[0]
        rows = c.execute(
            f"""
            SELECT e.id, e.user_id, e.event_type, e.created_at, e.meta,
                   u.username, u.name
            FROM events e LEFT JOIN users u ON u.tg_id = e.user_id
            {where_sql}
            ORDER BY e.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        distinct = [r[0] for r in c.execute(
            "SELECT DISTINCT event_type FROM events ORDER BY event_type"
        )]
    items = [{
        "id": r["id"], "user_id": r["user_id"], "username": r["username"],
        "name": r["name"], "event_type": r["event_type"],
        "created_at": r["created_at"], "meta": r["meta"],
    } for r in rows]
    return items, total, distinct


def count_broadcast_targets(segment: str) -> int:
    if segment == "all":
        with _conn() as c:
            return c.execute("SELECT COUNT(*) FROM users WHERE unsubscribed=0").fetchone()[0]
    if segment not in VALID_SEGMENTS:
        raise ValueError(f"Invalid segment: {segment}")
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM users WHERE unsubscribed=0 AND segment=?", (segment,)
        ).fetchone()[0]
