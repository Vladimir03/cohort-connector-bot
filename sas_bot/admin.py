"""Admin-only commands: /stats, /segment, /broadcast, /export, /test."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Dict

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

import db
from broadcast import send_document_to_users, send_to_users
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


# ---------- /broadcast_doc: send a document (PDF) with caption to a segment ----------

PENDING_DOC_TTL = 900  # 15 minutes
# admin_id -> {"segment", "stage": "doc"|"confirm", "file_id", "caption", "task"}
_pending_doc: Dict[int, dict] = {}


def _clear_pending_doc(admin_id: int) -> None:
    p = _pending_doc.pop(admin_id, None)
    if p:
        task = p.get("task")
        if task and not task.done():
            task.cancel()


async def _expire_pending_doc(admin_id: int) -> None:
    try:
        await asyncio.sleep(PENDING_DOC_TTL)
    except asyncio.CancelledError:
        return
    if _pending_doc.pop(admin_id, None) is not None:
        log.info("broadcast_doc pending expired for admin %s", admin_id)


def _segments_hint() -> str:
    return "Сегменты: " + ", ".join(sorted(db.VALID_SEGMENTS)) + ", all"


@router.message(Command("broadcast_doc"))
async def cmd_broadcast_doc(message: Message) -> None:
    if not _is_admin(message):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /broadcast_doc &lt;сегмент|all&gt;\n" + _segments_hint())
        return
    segment = parts[1].strip()
    if segment != "all" and segment not in db.VALID_SEGMENTS:
        await message.answer(f"Неизвестный сегмент: {segment}\n" + _segments_hint(), parse_mode=None)
        return

    admin_id = message.from_user.id
    _clear_pending_doc(admin_id)  # a new /broadcast_doc expires any previous flow
    task = asyncio.create_task(_expire_pending_doc(admin_id))
    _pending_doc[admin_id] = {
        "segment": segment, "stage": "doc",
        "file_id": None, "caption": None, "task": task,
    }
    await message.answer(
        "Пришли документ (PDF) с подписью — она уйдёт как caption. Поддерживается {name}."
    )


@router.message(F.document, F.from_user.id.in_(ADMIN_IDS))
async def on_admin_document(message: Message, bot: Bot) -> None:
    admin_id = message.from_user.id
    p = _pending_doc.get(admin_id)
    if not p or p["stage"] != "doc":
        return  # not awaiting a document for /broadcast_doc — ignore

    caption = message.caption or ""
    if len(caption) > 1000:
        await message.answer(
            f"Подпись слишком длинная: {len(caption)} символов, лимит 1000 "
            "(оставлен запас под подстановку имени). Сократи и пришли документ заново."
        )
        return  # stay in "doc" stage so the admin can retry

    p["file_id"] = message.document.file_id
    p["caption"] = caption
    p["stage"] = "confirm"

    segment = p["segment"]
    user = db.get_user(admin_id)
    admin_name = user["name"] if user else (message.from_user.first_name or "друг")
    try:
        preview = caption.format(name=admin_name)
    except Exception:
        preview = caption
    await bot.send_document(admin_id, document=p["file_id"], caption=preview or None, parse_mode=None)

    n = db.count_broadcast_targets(segment)
    await message.answer(
        f"Получателей: {n} (segment {segment}, unsubscribed исключены). "
        "Отправить всем — /confirm_doc, отменить — /cancel_doc"
    )


@router.message(Command("confirm_doc"))
async def cmd_confirm_doc(message: Message, bot: Bot) -> None:
    if not _is_admin(message):
        return
    admin_id = message.from_user.id
    p = _pending_doc.get(admin_id)
    if not p or p["stage"] != "confirm":
        await message.answer(
            "Нечего подтверждать. Начни с /broadcast_doc &lt;сегмент|all&gt; и пришли документ."
        )
        return

    segment, file_id, caption = p["segment"], p["file_id"], p["caption"]
    _clear_pending_doc(admin_id)  # consume now → prevents a double /confirm_doc

    members = db.get_segment_members(segment)
    await message.answer("Отправляю…")
    result = await send_document_to_users(bot, members, file_id, caption)
    await message.answer("Готово: " + json.dumps(result, ensure_ascii=False))


@router.message(Command("cancel_doc"))
async def cmd_cancel_doc(message: Message) -> None:
    if not _is_admin(message):
        return
    admin_id = message.from_user.id
    if admin_id in _pending_doc:
        _clear_pending_doc(admin_id)
        await message.answer("Отменено.")
    else:
        await message.answer("Нечего отменять.")
