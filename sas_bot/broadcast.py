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
