"""Entry point. Runs both aiogram polling and FastAPI web admin concurrently."""
from __future__ import annotations

import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import admin
import db
import handlers
from config import TELEGRAM_BOT_TOKEN, WEB_HOST, WEB_PORT
from scheduler import setup_scheduler
from web.api import app as web_app, set_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("bot")


async def run_bot(bot: Bot, dp: Dispatcher) -> None:
    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info("Scheduler started")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


async def run_web() -> None:
    config = uvicorn.Config(
        web_app, host=WEB_HOST, port=WEB_PORT, log_level="info",
        access_log=False, lifespan="on",
    )
    server = uvicorn.Server(config)
    log.info("Starting web admin on http://%s:%s", WEB_HOST, WEB_PORT)
    await server.serve()


async def main() -> None:
    db.init_db()
    log.info("DB initialized (WAL)")

    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(handlers.router)

    set_bot(bot)

    await asyncio.gather(run_bot(bot, dp), run_web())


if __name__ == "__main__":
    asyncio.run(main())
