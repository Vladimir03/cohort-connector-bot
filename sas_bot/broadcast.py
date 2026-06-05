"""Broadcast send helper, shared by scheduler and admin /broadcast."""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

import db

log = logging.getLogger(__name__)

SEND_DELAY = 0.05  # 50ms between sends → 20/sec, under Telegram's 30/sec limit
SEND_DELAY_DOC = 0.1  # documents: 100ms between sends (per /broadcast_doc spec)


async def send_to_users(bot: Bot, users: Iterable, text_template: str, job_id: str,
                        format_kwargs: dict | None = None) -> tuple[int, int]:
    sent = 0
    failed = 0
    for user in users:
        kwargs = {"name": user["name"] or "друг"}
        if format_kwargs:
            kwargs.update(format_kwargs)
        try:
            text = text_template.format(**kwargs)
        except Exception:
            text = text_template
        try:
            await bot.send_message(user["tg_id"], text, parse_mode="HTML",
                                   disable_web_page_preview=True)
            db.log_event(user["tg_id"], f"broadcast_{job_id}")
            sent += 1
        except TelegramRetryAfter as e:
            log.warning("Rate limited, sleeping %s", e.retry_after)
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(user["tg_id"], text, parse_mode="HTML",
                                       disable_web_page_preview=True)
                db.log_event(user["tg_id"], f"broadcast_{job_id}")
                sent += 1
            except Exception as e2:
                log.exception("Retry failed for %s: %s", user["tg_id"], e2)
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            log.info("User %s blocked/invalid: %s", user["tg_id"], e)
            db.set_unsubscribed(user["tg_id"], 1)
            db.log_event(user["tg_id"], f"broadcast_failed_{job_id}", {"error": str(e)})
            failed += 1
        except Exception as e:
            log.exception("Send error to %s: %s", user["tg_id"], e)
            db.log_event(user["tg_id"], f"broadcast_failed_{job_id}", {"error": str(e)})
            failed += 1
        await asyncio.sleep(SEND_DELAY)
    return sent, failed


async def send_document_to_users(bot: Bot, users: Iterable, file_id: str,
                                 caption: str) -> dict:
    """Send a document (by file_id) to users, skipping unsubscribed ones.

    Mirrors send_to_users: per-send rate limit, RetryAfter back-off, and
    Forbidden/BadRequest → mark unsubscribed. Returns delivery stats dict.
    """
    sent = failed = skipped = 0
    for user in users:
        if user["unsubscribed"]:
            skipped += 1
            continue
        try:
            cap = caption.format(name=user["name"] or "друг")
        except Exception:
            cap = caption
        cap = cap or None
        try:
            await bot.send_document(user["tg_id"], document=file_id, caption=cap, parse_mode=None)
            db.log_event(user["tg_id"], "broadcast_doc")
            sent += 1
        except TelegramRetryAfter as e:
            log.warning("Rate limited, sleeping %s", e.retry_after)
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_document(user["tg_id"], document=file_id, caption=cap, parse_mode=None)
                db.log_event(user["tg_id"], "broadcast_doc")
                sent += 1
            except Exception as e2:
                log.exception("Retry failed for %s: %s", user["tg_id"], e2)
                db.log_event(user["tg_id"], "broadcast_failed_doc", {"error": str(e2)})
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            log.info("User %s blocked/invalid: %s", user["tg_id"], e)
            db.set_unsubscribed(user["tg_id"], 1)
            db.log_event(user["tg_id"], "broadcast_failed_doc", {"error": str(e)})
            failed += 1
        except Exception as e:
            log.exception("Send error to %s: %s", user["tg_id"], e)
            db.log_event(user["tg_id"], "broadcast_failed_doc", {"error": str(e)})
            failed += 1
        await asyncio.sleep(SEND_DELAY_DOC)
    return {"sent": sent, "failed": failed, "skipped_unsubscribed": skipped}
