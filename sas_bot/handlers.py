"""User-facing handlers: /start, registration FSM, /help, /unsubscribe, /landing, /call."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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
from config import CALL_LINK, LANDING_URL, ZOOM_LINK
from content import (
    M0_WELCOME,
    M_ALREADY_REGISTERED,
    M_HELP,
    M_INTRO,
    M_UNSUBSCRIBE,
)

log = logging.getLogger(__name__)
router = Router()


class RegisterFlow(StatesGroup):
    waiting_name = State()
    waiting_role = State()


def _register_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Записаться на вебинар", callback_data="register")]
        ]
    )


def _role_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Product Analyst"), KeyboardButton(text="Marketing Analyst")],
            [KeyboardButton(text="Data Analyst"), KeyboardButton(text="Другое")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
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
    await cb.message.answer("Как тебя зовут? Можно одно имя.")


@router.message(RegisterFlow.waiting_name)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:64]
    if not name:
        await message.answer("Пожалуйста, напиши имя текстом.")
        return
    await state.update_data(name=name)
    await state.set_state(RegisterFlow.waiting_role)
    await message.answer("Кем работаешь сейчас?", reply_markup=_role_kb())


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
    await message.answer(M_HELP)


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
