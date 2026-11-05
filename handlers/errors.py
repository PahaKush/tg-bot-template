"""Единый роутер ошибок: подключается ПОСЛЕДНИМ в main.py.

Разделение простое: доменную ошибку (AppError) показываем как есть — она написана для
человека; всё остальное логируем с трассой и отвечаем общим текстом, потому что в
сообщении об ошибке легко утечь путям, SQL и внутренним именам.

Здесь же живут два catch-all для callback'ов. Без них клик по кнопке из старого сообщения
оставляет «часики» до таймаута — пользователь видит зависший интерфейс, а не отказ.
"""

import logging
from contextlib import suppress

from aiogram import F, Router, flags
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message
from tgkit import AppError

router = Router()


async def _reply(event: ErrorEvent, text: str, *, alert: bool = True) -> None:
    """Отвечает туда, откуда пришла ошибка: alert для кнопки, сообщение для текста."""
    update = event.update
    if update.callback_query:
        with suppress(Exception):
            await update.callback_query.answer(text, show_alert=alert)
        return
    if update.message:
        with suppress(Exception):
            await update.message.answer(text)


@router.error(ExceptionTypeFilter(TelegramBadRequest), F.update.callback_query.as_("callback"))
async def handle_telegram_bad_request(event: ErrorEvent, callback: CallbackQuery, state: FSMContext) -> None:
    """«message is not modified» — не ошибка, а повторный клик по той же кнопке."""
    if "message is not modified" in str(event.exception):
        logging.debug("Игнорирую: %s", event.exception)
        with suppress(Exception):
            await callback.answer()
        return
    await handle_unknown_error(event, callback, state)


@router.error(ExceptionTypeFilter(AppError))
async def handle_app_errors(event: ErrorEvent) -> None:
    """Доменные ошибки. Стейт НЕ сбрасываем: флоу сам решает, продолжать или нет —
    иначе опечатка в одном поле выбрасывала бы пользователя из всей формы."""
    message = getattr(event.exception, "user_message", None) or str(event.exception)
    await _reply(event, message)


@router.error(F.update.callback_query.as_("callback"))
async def handle_unknown_error(event: ErrorEvent, callback: CallbackQuery, state: FSMContext) -> None:
    logging.error("Необработанная ошибка: %s", event.exception, exc_info=True)
    with suppress(Exception):
        await state.clear()
        await callback.answer("Произошла ошибка ⚠️. Процесс прерван.", show_alert=True)


@router.error(F.update.message.as_("message"))
async def handle_unknown_message_error(event: ErrorEvent, message: Message, state: FSMContext) -> None:
    """Без этой ветки исключение в message-хендлере aiogram просто залогирует и дропнет —
    пользователь не увидит ничего и будет ждать ответа."""
    logging.error("Необработанная ошибка в message-хендлере: %s", event.exception, exc_info=True)
    with suppress(Exception):
        await state.clear()
        await message.answer("Произошла ошибка ⚠️. Процесс прерван.")


@router.callback_query(F.data == "ignore")
@flags.keep_state
async def handle_ignore_callback(callback: CallbackQuery) -> None:
    """Декоративные кнопки (индикатор страницы «1/3», «(Пока пусто)»).

    Нужен именно хендлер: CallbackAnswerMiddleware — inner-мидлварь и срабатывает ТОЛЬКО
    после совпадения фильтра, поэтому без него «часики» висели бы до таймаута.
    """
    with suppress(Exception):
        await callback.answer()


@router.callback_query()
@flags.keep_state  # клик по мёртвой кнопке старого сообщения не должен рвать текущий ввод
async def handle_stale_callback(callback: CallbackQuery) -> None:
    """Catch-all для кнопок из устаревших сообщений (например, после сброса FSM)."""
    logging.debug("Устаревший callback без хендлера: %s", callback.data)
    with suppress(Exception):
        await callback.answer("⚠️ Меню устарело. Откройте заново: /start", show_alert=True)
