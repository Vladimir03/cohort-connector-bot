"""FastAPI web admin dashboard. Shares SQLite DB and bot instance with aiogram process."""
from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
from broadcast import send_to_users
from config import ADMIN_PASSWORD, ADMIN_USERNAME

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SAS Bot Admin", docs_url=None, redoc_url=None, openapi_url=None)

# Shared state with bot.py — set at startup
_state: dict = {"bot": None}


def set_bot(bot_instance) -> None:
    _state["bot"] = bot_instance


security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    ok_user = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    ok_pass = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="SAS Bot Admin"'},
        )
    return credentials.username


# ---------- Public ----------

@app.get("/health")
def health():
    return {"status": "ok", "bot_running": _state["bot"] is not None}


# ---------- Stats ----------

@app.get("/api/stats")
def api_stats(_: str = Depends(require_admin)):
    return db.stats_extended()


@app.get("/api/funnel")
def api_funnel(_: str = Depends(require_admin)):
    return db.funnel()


@app.get("/api/timeline")
def api_timeline(
    bucket: str = Query("hour", pattern="^(hour|day)$"),
    days: int = Query(7),
    _: str = Depends(require_admin),
):
    if days not in (1, 7, 30):
        raise HTTPException(400, "days must be 1, 7, or 30")
    try:
        return db.timeline(bucket=bucket, days=days)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- Users ----------

@app.get("/api/users")
def api_users(
    segment: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: str = Depends(require_admin),
):
    try:
        items, total = db.list_users(segment or None, search or None, limit, offset)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/api/users/{tg_id}")
def api_user_detail(tg_id: int, _: str = Depends(require_admin)):
    details = db.get_user_details(tg_id)
    if not details:
        raise HTTPException(404, "User not found")
    return details


class SegmentBody(BaseModel):
    segment: str


@app.post("/api/users/{tg_id}/segment")
def api_user_set_segment(tg_id: int, body: SegmentBody, _: str = Depends(require_admin)):
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(404, "User not found")
    prev = user["segment"]
    if body.segment not in db.VALID_SEGMENTS:
        raise HTTPException(400, f"Invalid segment: {body.segment}")
    db.set_segment(tg_id, body.segment)
    db.log_event(tg_id, "admin_segment_change", {"from": prev, "to": body.segment})
    return db.get_user_details(tg_id)


@app.post("/api/users/{tg_id}/unsubscribe")
def api_user_unsubscribe(tg_id: int, _: str = Depends(require_admin)):
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(404, "User not found")
    db.set_unsubscribed(tg_id, 1)
    db.log_event(tg_id, "admin_unsubscribe")
    return db.get_user_details(tg_id)


# ---------- Events ----------

@app.get("/api/events")
def api_events(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    _: str = Depends(require_admin),
):
    items, total, types = db.list_events(event_type or None, user_id, limit, offset)
    return {"items": items, "total": total, "types": types,
            "limit": limit, "offset": offset}


# ---------- Broadcast ----------

class BroadcastBody(BaseModel):
    segment: str
    text: str = Field(min_length=1, max_length=4000)
    preview: bool = False


@app.post("/api/broadcast")
async def api_broadcast(body: BroadcastBody, _: str = Depends(require_admin)):
    seg = body.segment
    if seg == "all":
        users = db.get_users_for_broadcast(list(db.VALID_SEGMENTS))
    else:
        if seg not in db.VALID_SEGMENTS:
            raise HTTPException(400, f"Invalid segment: {seg}")
        users = db.get_users_for_broadcast([seg])

    if body.preview:
        return {"preview": True, "would_send_to": len(users)}

    bot = _state["bot"]
    if bot is None:
        raise HTTPException(503, "Bot not initialised")
    sent, failed = await send_to_users(bot, users, body.text, job_id="admin_web")
    return {"sent": sent, "failed": failed, "skipped_unsubscribed": 0,
            "total_targets": len(users)}


# ---------- Static frontend (SPA) ----------

INDEX_HTML = STATIC_DIR / "index.html"


@app.get("/")
def root():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return JSONResponse(
        {"error": "Frontend not built. Run `cd web/frontend && npm install && npm run build`."},
        status_code=503,
    )


# Mount built assets (Vite outputs /assets/*). Mount AFTER routes so /api/* wins.
if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


# SPA fallback: any non-/api path returns index.html (so client-side routing works)
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path == "health":
        raise HTTPException(404, "Not Found")
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    raise HTTPException(404, "Frontend not built")
