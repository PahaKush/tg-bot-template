"""Команды: /start, /stats, /settings, /broadcast.

Админ-команды закрыты фильтром IsAdmin: для остальных их просто нет, и на них бот отвечает
так же, как на любую неизвестную команду. Коллбэки админки размечены Access.ADMIN.
"""

from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User
from dishka.integrations.aiogram import FromDishka
from tgkit import StateHelper
from tgkit.filters import IsAdmin
from tgkit.kb import cancel_btn, confirm_kb
from tgkit.utils.delivery import broadcast
from tgkit.utils.formatting import esc
from tgkit.utils.telegram import load_payload

from repositories import NotesRepository, SettingsRepository, UserRepository
from services.settings_manager import SettingsManager

from models.callbacks import BroadcastSendCB, SettingsCB
from models.fsm_payloads import BroadcastPayload
from modules.fsm_states import Broadcast
from modules.keyboards import settings_kb, start_kb

router = Router()


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


@router.message(Command("settings"), IsAdmin())
async def handle_settings_command(message: Message, settings_repo: FromDishka[SettingsRepository]) -> None:
    debug = await settings_repo.get_log_level() == "DEBUG"
    await message.answer("Настройки:", reply_markup=settings_kb(debug))


@router.callback_query(SettingsCB.filter())
async def handle_settings_toggle(
    callback: CallbackQuery,
    callback_data: SettingsCB,
    callback_msg: Message,
    settings_manager: FromDishka[SettingsManager],
) -> None:
    debug = await settings_manager.toggle_setting(callback_data.prop, callback_data.act)
    await callback_msg.edit_text("Настройки:", reply_markup=settings_kb(debug))


@router.message(Command("stats"), IsAdmin())
async def handle_stats_command(
    message: Message,
    event_from_user: User,
    user_repo: FromDishka[UserRepository],
    notes_repo: FromDishka[NotesRepository],
) -> None:
    await message.answer(
        f"👥 Пользователей: <b>{await user_repo.count()}</b>\n"
        f"📝 Ваших заметок: <b>{await notes_repo.count_for_user(event_from_user.id)}</b>"
    )


@router.message(Command("broadcast"), IsAdmin())
async def handle_broadcast_command(message: Message, state: FSMContext) -> None:
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
    payload = await load_payload(state, BroadcastPayload, callback)
    if payload is None:
        return
    # До отправки: повторный клик по «Отправить» во время долгой рассылки запустил бы вторую.
    await state.clear()

    user_ids = await user_repo.get_all_user_ids()
    await callback_msg.edit_text(f"📢 Отправляю {len(user_ids)}…")
    report = await broadcast(bot, user_ids, payload.text)

    summary = f"Доставлено: {report.delivered}\nНедоступны: {report.unreachable}\nОшибки: {report.failed}"
    if report.aborted:
        summary += "\n\n⚠️ Telegram не принял текст, рассылка остановлена."
    with suppress(Exception):
        await callback_msg.edit_text(f"📢 <b>Рассылка завершена</b>\n\n{summary}")
