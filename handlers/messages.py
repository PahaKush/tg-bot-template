"""Фолбэк на нераспознанный ввод.

Регистрируется ПОСЛЕ всех FSM-хендлеров и только для состояния None: иначе он перехватывал
бы шаги многошаговых флоу, и ввод заголовка заметки превращался бы в «Не понял».
"""

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message

router = Router()


@router.message(StateFilter(None))
async def handle_unknown_message(message: Message):
    await message.answer("Не понял. Откройте меню: /start")
