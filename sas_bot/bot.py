"""Entry point. Run with: python bot.py"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import admin
import db
import handlers
from config import TELEGRAM_BOT_TOKEN
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("bot")


async def main() -> None:
    db.init_db()
    log.info("DB initialized")

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Admin router first so /broadcast etc. take priority
    dp.include_router(admin.router)
    dp.include_router(handlers.router)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info("Scheduler started")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
