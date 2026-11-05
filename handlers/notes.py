"""Демо-фича, которая прогоняет весь каркас.

По ней видно все паттерны сразу: типизированный коллбэк с разметкой доступа, скоуп владения
в SQL, транзакция в сервисе, экран ошибки с сохранением навигации, пагинация.

Копируйте этот файл как образец для своей фичи.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User
from dishka.integrations.aiogram import FromDishka
from tgkit import StateHelper
from tgkit.kb import back_btn, cancel_btn
from tgkit.utils.error_screen import edit, error_screen, reply
from tgkit.utils.formatting import esc, format_db_timestamp
from tgkit.utils.telegram import load_payload

from repositories import NotesRepository
from services.notes_manager import NotesManager

from models.callbacks import NoteColorCB, NoteDeleteCB, NoteListCB, NoteViewCB
from models.enums import NoteColor
from models.fsm_payloads import NoteCreationPayload
from modules.fsm_states import AddNote
from modules.keyboards import note_view_kb, notes_list_kb

router = Router()


async def render_notes_list(message: Message, user_id: int, notes_repo: NotesRepository, page: int = 0) -> None:
    """Единственная точка отрисовки списка.

    Общая функция, а не копия в каждом хендлере: иначе экран после удаления и экран после
    пагинации начинают расходиться, и расхождение замечают не сразу.
    """
    notes = await notes_repo.list_for_user(user_id)
    await message.edit_text(f"📝 <b>Ваши заметки:</b> {len(notes)}", reply_markup=notes_list_kb(notes, page))


async def render_note(message: Message, note: dict) -> None:
    """Единственная точка отрисовки карточки — по той же причине, что и у списка."""
    color = NoteColor(note["color"])
    await message.edit_text(
        f"{color.icon} <b>{esc(note['title'])}</b>\n"
        f"<i>{format_db_timestamp(note['created_at'])}</i>\n\n"
        f"{esc(note['body'])}",
        reply_markup=note_view_kb(note["id"], color),
    )


@router.callback_query(NoteListCB.filter())
async def handle_notes_list(
    callback: CallbackQuery,
    callback_data: NoteListCB,
    callback_msg: Message,
    notes_repo: FromDishka[NotesRepository],
):
    await render_notes_list(callback_msg, callback.from_user.id, notes_repo, callback_data.page)


@router.callback_query(NoteViewCB.filter())
async def handle_note_view(
    callback: CallbackQuery,
    callback_data: NoteViewCB,
    callback_msg: Message,
    notes_manager: FromDishka[NotesManager],
):
    """Карточка заметки.

    note_id пришёл из callback_data, то есть от клиента. Принадлежность проверяет
    NotesManager.get_note -> SQL со скоупом по user_id; чужая заметка неотличима от
    несуществующей.
    """
    async with error_screen(edit(callback_msg), "❌ Не удалось открыть заметку.", NoteListCB()):
        note = await notes_manager.get_note(callback_data.note_id, callback.from_user.id)
        await render_note(callback_msg, note)


@router.callback_query(NoteColorCB.filter())
async def handle_note_color(
    callback: CallbackQuery,
    callback_data: NoteColorCB,
    callback_msg: Message,
    notes_manager: FromDishka[NotesManager],
):
    async with error_screen(edit(callback_msg), "❌ Не удалось изменить метку.", NoteListCB()):
        await notes_manager.set_color(callback_data.note_id, callback.from_user.id, callback_data.color)
        note = await notes_manager.get_note(callback_data.note_id, callback.from_user.id)
        await render_note(callback_msg, note)


@router.callback_query(NoteDeleteCB.filter())
async def handle_note_delete(
    callback: CallbackQuery,
    callback_data: NoteDeleteCB,
    callback_msg: Message,
    notes_manager: FromDishka[NotesManager],
    notes_repo: FromDishka[NotesRepository],
):
    async with error_screen(edit(callback_msg), "❌ Не удалось удалить.", NoteListCB()) as screen:
        await notes_manager.delete_note(callback_data.note_id, callback.from_user.id)
    if screen.failed:
        return

    await callback.answer("Удалено")
    await render_notes_list(callback_msg, callback.from_user.id, notes_repo)


# --- Многошаговый ввод ---------------------------------------------------------


@router.callback_query(F.data == "note_new")
async def handle_note_new(callback: CallbackQuery, callback_msg: Message, state: FSMContext):
    await StateHelper.save(state, NoteCreationPayload())
    await callback_msg.edit_text("Введите заголовок заметки:", reply_markup=cancel_btn(NoteListCB()))
    await state.set_state(AddNote.waiting_for_title)


@router.message(AddNote.waiting_for_title)
async def handle_note_title(message: Message, state: FSMContext):
    payload = await load_payload(state, NoteCreationPayload, message, clear=False)
    if payload is None:
        return

    payload.title = (message.text or "").strip()
    if not payload.title:
        await message.answer("⚠️ Нужен текст. Введите заголовок:")
        return

    await StateHelper.save(state, payload)
    await message.answer("Теперь введите текст заметки:")
    await state.set_state(AddNote.waiting_for_body)


@router.message(AddNote.waiting_for_body)
async def handle_note_body(
    message: Message,
    state: FSMContext,
    event_from_user: User,
    notes_manager: FromDishka[NotesManager],
):
    """Терминальный шаг: владеет очисткой стейта на ЛЮБОМ исходе.

    Стейт чистится в finally, а не после успеха: иначе ошибка сохранения оставляла бы
    пользователя внутри флоу без единой подсказки, что делать дальше.
    """
    payload = await load_payload(state, NoteCreationPayload, message, clear=False)
    if payload is None or not payload.title:
        return

    try:
        async with error_screen(reply(message), "❌ Не удалось сохранить заметку.", NoteListCB()) as screen:
            await notes_manager.add_note(event_from_user.id, payload.title, message.text or "")
        if not screen.failed:
            await message.answer("✅ Заметка сохранена.", reply_markup=back_btn(NoteListCB()))
    finally:
        await state.clear()
