"""Admin-only commands: /stats, /segment, /broadcast, /export, /test."""
from __future__ import annotations

import logging
import os
import tempfile

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

import db
from broadcast import send_to_users
from config import ADMIN_IDS, CALL_LINK, LANDING_URL, ZOOM_LINK
from content import BROADCAST_TEMPLATES

log = logging.getLogger(__name__)
router = Router()


def _is_admin(message: Message) -> bool:
    return message.from_user and message.from_user.id in ADMIN_IDS


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message):
        return
    s = db.stats()
    lines = [f"Всего пользователей: {s['total']}", f"Отписалось: {s['unsubscribed']}", "", "По сегментам:"]
    for seg, n in sorted(s["by_segment"].items()):
        lines.append(f"  {seg}: {n}")
    await message.answer("\n".join(lines))


@router.message(Command("segment"))
async def cmd_segment(message: Message) -> None:
    if not _is_admin(message):
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /segment <tg_id|@username> <segment>")
        return
    ident, seg = parts[1], parts[2].strip()
    user = db.find_user(ident)
    if not user:
        await message.answer(f"Пользователь не найден: {ident}")
        return
    try:
        db.set_segment(user["tg_id"], seg)
    except ValueError as e:
        await message.answer(str(e))
        return
    await message.answer(f"OK: {user['tg_id']} → {seg}")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    if not _is_admin(message):
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /broadcast <segment|all> <text>")
        return
    target, text = parts[1], parts[2]
    if target == "all":
        users = db.get_users_for_broadcast(list(db.VALID_SEGMENTS))
    else:
        if target not in db.VALID_SEGMENTS:
            await message.answer(f"Неизвестный сегмент: {target}")
            return
        users = db.get_users_for_broadcast([target])
    sent, failed = await send_to_users(bot, users, text, job_id="manual")
    await message.answer(f"Отправлено: {sent}, ошибок: {failed}")


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    if not _is_admin(message):
        return
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp.close()
    db.export_csv(tmp.name)
    await message.answer_document(FSInputFile(tmp.name, filename="users.csv"))
    os.unlink(tmp.name)


@router.message(Command("test"))
async def cmd_test(message: Message) -> None:
    if not _is_admin(message):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /test <message_id>\nДоступно: " + ", ".join(BROADCAST_TEMPLATES))
        return
    mid = parts[1].strip()
    tpl = BROADCAST_TEMPLATES.get(mid)
    if not tpl:
        await message.answer(f"Нет шаблона: {mid}")
        return
    user = db.get_user(message.from_user.id)
    name = user["name"] if user else (message.from_user.first_name or "друг")
    rendered = tpl.format(name=name, zoom_link=ZOOM_LINK, landing_url=LANDING_URL, call_link=CALL_LINK)
    await message.answer(rendered, disable_web_page_preview=True)
