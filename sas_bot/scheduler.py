"""APScheduler setup for nurturing broadcasts."""
from __future__ import annotations

import logging
from datetime import datetime

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

import db
from broadcast import send_to_users
from config import CALL_LINK, LANDING_URL, TIMEZONE, ZOOM_LINK
from content import (
    M1_DAY_BEFORE, M2_ONE_HOUR, M3_THANKS, M4_REVEAL,
    M5_FAQ, M6_OPEN, M7_DEADLINE,
)

log = logging.getLogger(__name__)
TZ = pytz.timezone(TIMEZONE)

FORMAT_KWARGS = {"zoom_link": ZOOM_LINK, "landing_url": LANDING_URL, "call_link": CALL_LINK}


# (job_id, run_at_msk, template, target_filter)
# target_filter: ("in", [segments]) or ("not_in", [segments])
JOBS = [
    ("m1_day_before", datetime(2026, 6, 3, 19, 0), M1_DAY_BEFORE, ("in", ["pre_webinar"])),
    ("m2_one_hour",   datetime(2026, 6, 4, 18, 0), M2_ONE_HOUR,   ("in", ["pre_webinar"])),
    ("m3_thanks",     datetime(2026, 6, 4, 21, 0), M3_THANKS,
        ("in", ["pre_webinar", "attended_live", "no_show"])),
    ("m4_reveal",     datetime(2026, 6, 5, 11, 0), M4_REVEAL,
        ("not_in", ["customer", "churned"])),
    ("m5_faq",        datetime(2026, 6, 7, 11, 0), M5_FAQ,
        ("not_in", ["customer", "churned"])),
    ("m6_open",       datetime(2026, 6, 9, 11, 0), M6_OPEN,
        ("not_in", ["customer", "churned"])),
    ("m7_deadline",   datetime(2026, 6, 11, 11, 0), M7_DEADLINE,
        ("in", ["hot_lead"])),
]


async def _run_job(bot: Bot, job_id: str, template: str, filter_kind: str, segments: list[str]) -> None:
    log.info("Running broadcast %s", job_id)
    try:
        if filter_kind == "in":
            users = db.get_users_for_broadcast(segments)
        else:
            users = db.get_users_not_in_segments(segments)
        # Idempotency: drop anyone who already received this broadcast, so a
        # restart within the misfire window can't double-send to the same people.
        already = db.users_already_sent(job_id)
        users = [u for u in users if u["tg_id"] not in already]
        if not users:
            log.info("Broadcast %s: nothing to send (everyone already got it)", job_id)
            return
        sent, failed = await send_to_users(bot, users, template, job_id, FORMAT_KWARGS)
        log.info("Broadcast %s: sent=%d failed=%d", job_id, sent, failed)
    except Exception:
        log.exception("Broadcast %s crashed", job_id)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    # In-memory jobstore (the default). We intentionally do NOT use a persistent
    # SQLAlchemyJobStore: it pickles every job into SQLite, and the aiogram Bot
    # held in the job args contains an SSLContext that can't be pickled
    # ("TypeError: cannot pickle 'SSLContext' object"). The 7 jobs are re-created
    # from JOBS on every startup, so persistence isn't needed.
    scheduler = AsyncIOScheduler(timezone=TZ)
    for job_id, dt_naive, template, (filter_kind, segments) in JOBS:
        run_at = TZ.localize(dt_naive)
        scheduler.add_job(
            _run_job,
            trigger=DateTrigger(run_date=run_at),
            args=[bot, job_id, template, filter_kind, segments],
            id=job_id,
            misfire_grace_time=3600,
            replace_existing=True,
        )
        log.info("Scheduled %s at %s", job_id, run_at)
    return scheduler
