"""Команды: /start, /stats, /settings, /broadcast.

Здесь же образец админ-гейта. Обратите внимание: у команд нет callback_data, значит
AccessControlMiddleware их не проверяет — гейт стоит в самом хендлере, явной строкой.
"""

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User
from dishka.integrations.aiogram import FromDishka
from tgkit import StateHelper
from tgkit.kb import cancel_btn, confirm_kb
from tgkit.utils.delivery import undeliverable_reason
from tgkit.utils.formatting import esc
from tgkit.utils.telegram import load_payload

from repositories import NotesRepository, SettingsRepository, UserRepository
from services.settings_manager import SettingsManager

from models.callbacks import BroadcastSendCB, SettingsCB
from models.fsm_payloads import BroadcastPayload
from modules.fsm_states import Broadcast
from modules.keyboards import settings_kb, start_kb

router = Router()

BROADCAST_PAUSE = 0.05  # ~20 сообщений/с — лимит Bot API на рассылку


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, event_from_user: User, is_admin: bool) -> None:
    await state.clear()
    role = " (админ)" if is_admin else ""
    await message.answer(
        f"Привет, {esc(event_from_user.first_name)}{role}! 👋\nШаблон бота с заметками.",
        reply_markup=start_kb(),
    )


@router.callback_query(F.data == "start_menu")
async def handle_start_menu(callback: CallbackQuery, callback_msg: Message, state: FSMContext) -> None:
    await state.clear()
    await callback_msg.edit_text("Главное меню:", reply_markup=start_kb())


@router.message(Command("settings"))
async def handle_settings_command(
    message: Message, is_admin: bool, settings_repo: FromDishka[SettingsRepository]
) -> None:
    if not is_admin:
        return  # молча: существование админ-команд не стоит подтверждать посторонним

    debug = await settings_repo.get_log_level() == "DEBUG"
    await message.answer("Настройки:", reply_markup=settings_kb(debug))


@router.callback_query(SettingsCB.filter())
async def handle_settings_toggle(
    callback: CallbackQuery,
    callback_data: SettingsCB,
    callback_msg: Message,
    settings_manager: FromDishka[SettingsManager],
) -> None:
    """Гейт по админу здесь НЕ нужен: SettingsCB размечен Access.ADMIN, и мидлварь уже
    отсекла чужих. Это и есть смысл разметки — не дублировать проверку в каждом хендлере."""
    debug = await settings_manager.toggle_setting(callback_data.prop, callback_data.act)
    await callback_msg.edit_text("Настройки:", reply_markup=settings_kb(debug))


@router.message(Command("stats"))
async def handle_stats_command(
    message: Message,
    event_from_user: User,
    is_admin: bool,
    user_repo: FromDishka[UserRepository],
    notes_repo: FromDishka[NotesRepository],
) -> None:
    if not is_admin:
        return
    await message.answer(
        f"👥 Пользователей: <b>{await user_repo.count()}</b>\n"
        f"📝 Ваших заметок: <b>{await notes_repo.count_for_user(event_from_user.id)}</b>"
    )


@router.message(Command("broadcast"))
async def handle_broadcast_command(message: Message, state: FSMContext, is_admin: bool) -> None:
    if not is_admin:
        return
    await state.set_state(Broadcast.waiting_for_text)
    await message.answer("Отправьте текст рассылки:", reply_markup=cancel_btn("start_menu"))


@router.message(Broadcast.waiting_for_text)
async def handle_broadcast_text(message: Message, state: FSMContext, user_repo: FromDishka[UserRepository]) -> None:
    # html_text, а не text: бот шлёт с parse_mode=HTML, и сырой «<» сорвал бы отправку
    # каждому получателю. Заодно сохраняется форматирование, которое набрал админ.
    text = message.html_text
    if not text or text.startswith("/"):
        await message.answer(
            "⚠️ Нужен текст рассылки, а не команда. Отправьте текст или нажмите «Отмена».",
            reply_markup=cancel_btn("start_menu"),
        )
        return

    await StateHelper.save(state, BroadcastPayload(text=text))
    await state.set_state(Broadcast.confirming)
    await message.answer(text)
    await message.answer(
        f"Разослать это сообщение всем пользователям ({await user_repo.count()})?",
        reply_markup=confirm_kb(BroadcastSendCB(), "start_menu", yes_text="📢 Отправить", no_text="Отмена ❌"),
    )


@router.callback_query(Broadcast.confirming, BroadcastSendCB.filter())
async def handle_broadcast_send(
    callback: CallbackQuery,
    callback_msg: Message,
    state: FSMContext,
    bot: Bot,
    user_repo: FromDishka[UserRepository],
) -> None:
    """Рассылка с паузой и подсчётом недоставленных.

    Пауза обязательна: без неё Bot API начнёт отвечать 429, и часть получателей молча
    выпадет. Ошибки доставки не прерывают рассылку — они ожидаемы (tgkit.utils.delivery).
    """
    payload = await load_payload(state, BroadcastPayload, callback)
    if payload is None:
        return
    # До отправки: повторный клик по «Отправить» во время долгой рассылки запустил бы вторую.
    await state.clear()

    user_ids = await user_repo.get_all_user_ids()
    await callback_msg.edit_text(f"📢 Отправляю {len(user_ids)}…")

    sent = unreachable = failed = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, payload.text)
            sent += 1
        except Exception as e:
            if undeliverable_reason(e):
                unreachable += 1  # не запускал бота или заблокировал — это не сбой
            else:
                failed += 1
                logging.warning("Рассылка: %s -> %s", user_id, e)
        await asyncio.sleep(BROADCAST_PAUSE)

    with suppress(Exception):
        await callback_msg.edit_text(
            f"📢 <b>Рассылка завершена</b>\n\nДоставлено: {sent}\nНедоступны: {unreachable}\nОшибки: {failed}"
        )
