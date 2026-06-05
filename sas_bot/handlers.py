"""User-facing handlers: /start, registration FSM, /help, /unsubscribe, /landing, /call, /zoom,
plus two-way message forwarding between users and admins."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import db
from config import ADMIN_IDS, CALL_LINK, LANDING_URL, ZOOM_LINK
from content import (
    M0_WELCOME,
    M_ALREADY_REGISTERED,
    M_HELP,
    M_HELP_ADMIN,
    M_INTRO,
    M_NAME_PROMPT,
    M_ROLE_PROMPT,
    M_UNSUBSCRIBE,
    M_ZOOM,
    M_ZOOM_NOT_REGISTERED,
)

log = logging.getLogger(__name__)
router = Router()

REPLY_TIMEOUT = 600  # 10 minutes

# In-memory: target_tg_id -> admin_id (whoever clicked "Ответить" first holds the lock)
_reply_locks: Dict[int, int] = {}
# admin_id -> asyncio.Task for auto-clear timeout
_reply_timeout_tasks: Dict[int, asyncio.Task] = {}


class RegisterFlow(StatesGroup):
    waiting_name = State()
    waiting_role = State()


class ReplyFlow(StatesGroup):
    waiting_text = State()


def _register_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Записаться на вебинар", callback_data="register")]
        ]
    )


def _role_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Продуктовый аналитик"), KeyboardButton(text="Маркетинговый аналитик")],
            [KeyboardButton(text="Дата-аналитик"), KeyboardButton(text="Другое")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _reply_kb(target_tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ответить", callback_data=f"reply:{target_tg_id}")]
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = db.get_user(message.from_user.id)
    if user and not user["unsubscribed"]:
        await message.answer(
            M_ALREADY_REGISTERED.format(name=user["name"], zoom_link=ZOOM_LINK),
            disable_web_page_preview=True,
        )
        return
    await message.answer(M_INTRO, reply_markup=_register_kb(), disable_web_page_preview=True)


@router.callback_query(F.data == "register")
async def cb_register(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(RegisterFlow.waiting_name)
    await cb.message.answer(M_NAME_PROMPT)


@router.message(RegisterFlow.waiting_name)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:64]
    if not name:
        await message.answer("Пожалуйста, напиши имя текстом.")
        return
    await state.update_data(name=name)
    await state.set_state(RegisterFlow.waiting_role)
    await message.answer(M_ROLE_PROMPT, reply_markup=_role_kb())


@router.message(RegisterFlow.waiting_role)
async def reg_role(message: Message, state: FSMContext) -> None:
    role = (message.text or "").strip()[:128]
    data = await state.get_data()
    name = data.get("name", "друг")
    tg_id = message.from_user.id
    username = message.from_user.username

    db.upsert_user(tg_id, username, name, role)
    db.log_event(tg_id, "registered", {"role": role})
    await state.clear()
    await message.answer(
        M0_WELCOME.format(name=name, zoom_link=ZOOM_LINK),
        reply_markup=ReplyKeyboardRemove(),
        disable_web_page_preview=True,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = M_HELP
    if message.from_user and message.from_user.id in ADMIN_IDS:
        text += "\n\n" + M_HELP_ADMIN
    await message.answer(text)


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message) -> None:
    db.set_unsubscribed(message.from_user.id, 1)
    db.log_event(message.from_user.id, "unsubscribed")
    await message.answer(M_UNSUBSCRIBE)


@router.message(Command("landing"))
async def cmd_landing(message: Message) -> None:
    db.log_event(message.from_user.id, "clicked_landing")
    await message.answer(
        f"Программа Senior Analyst Studio: {LANDING_URL}",
        disable_web_page_preview=False,
    )


@router.message(Command("call"))
async def cmd_call(message: Message) -> None:
    db.log_event(message.from_user.id, "clicked_call")
    await message.answer(
        f"30-минутный созвон с Владимиром: {CALL_LINK}",
        disable_web_page_preview=False,
    )


@router.message(Command("zoom"))
async def cmd_zoom(message: Message) -> None:
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(M_ZOOM_NOT_REGISTERED)
        return
    db.log_event(message.from_user.id, "clicked_zoom")
    await message.answer(M_ZOOM.format(zoom_link=ZOOM_LINK), disable_web_page_preview=True)


# ---------- Admin reply flow ----------

async def _auto_clear_reply(admin_id: int, target_tg_id: int, state: FSMContext) -> None:
    try:
        await asyncio.sleep(REPLY_TIMEOUT)
        cur = await state.get_state()
        if cur == ReplyFlow.waiting_text.state:
            data = await state.get_data()
            if data.get("reply_target") == target_tg_id:
                await state.clear()
                if _reply_locks.get(target_tg_id) == admin_id:
                    _reply_locks.pop(target_tg_id, None)
                log.info("Reply FSM auto-cleared for admin %s → %s", admin_id, target_tg_id)
    except asyncio.CancelledError:
        pass
    finally:
        _reply_timeout_tasks.pop(admin_id, None)


@router.callback_query(F.data.startswith("reply:"))
async def cb_reply(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not cb.from_user or cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только для админов", show_alert=True)
        return
    try:
        target_tg_id = int(cb.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await cb.answer("Bad callback")
        return

    admin_id = cb.from_user.id
    locked_by = _reply_locks.get(target_tg_id)
    if locked_by is not None and locked_by != admin_id:
        await cb.answer("Уже отвечает другой админ", show_alert=True)
        return

    _reply_locks[target_tg_id] = admin_id

    # Set state for THIS admin (state context is scoped to the callback's user/chat already)
    await state.set_state(ReplyFlow.waiting_text)
    await state.update_data(reply_target=target_tg_id)

    # Cancel any prior timeout for this admin
    prev = _reply_timeout_tasks.pop(admin_id, None)
    if prev and not prev.done():
        prev.cancel()
    _reply_timeout_tasks[admin_id] = asyncio.create_task(
        _auto_clear_reply(admin_id, target_tg_id, state)
    )

    await cb.answer()
    await bot.send_message(
        admin_id,
        f"✍️ Напиши ответ для tg_id={target_tg_id} (10 минут). Любое сообщение будет отправлено как ответ.",
    )


@router.message(ReplyFlow.waiting_text, F.from_user.id.in_(ADMIN_IDS))
async def admin_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    target_tg_id = data.get("reply_target")
    text = (message.text or "").strip()
    if not target_tg_id or not text:
        await message.answer("Пустой ответ, отмена. Нажми «Ответить» заново.")
        await state.clear()
        return

    try:
        await bot.send_message(target_tg_id, text)
    except Exception as e:
        log.exception("Failed to deliver admin reply to %s", target_tg_id)
        await message.answer(f"Не удалось доставить: {e}")
        await state.clear()
        _reply_locks.pop(target_tg_id, None)
        task = _reply_timeout_tasks.pop(message.from_user.id, None)
        if task and not task.done():
            task.cancel()
        return

    db.log_event(message.from_user.id, "admin_reply_sent",
                 {"to": target_tg_id, "text": text[:200]})
    await message.answer(f"✅ Отправлено tg_id={target_tg_id}")

    await state.clear()
    _reply_locks.pop(target_tg_id, None)
    task = _reply_timeout_tasks.pop(message.from_user.id, None)
    if task and not task.done():
        task.cancel()


# ---------- Catch-all: forward user messages to admins ----------

@router.message(F.text & ~F.text.startswith("/") & ~F.from_user.id.in_(ADMIN_IDS))
async def forward_to_admins(message: Message, bot: Bot) -> None:
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(M_ZOOM_NOT_REGISTERED)
        return

    tg_id = message.from_user.id
    text = message.text or ""
    db.log_event(tg_id, "user_message_received", {"text": text[:200]})

    uname = f"@{user['username']}" if user["username"] else "—"
    formatted = (
        f"💬 От {uname} ({user['name']}, {user['role']}, tg_id={tg_id}):\n\n{text}"
    )
    kb = _reply_kb(tg_id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, formatted, reply_markup=kb,
                                   disable_web_page_preview=True)
        except Exception:
            log.exception("Failed to forward to admin %s", admin_id)

    await message.answer("Принял, отвечу лично 👌")
