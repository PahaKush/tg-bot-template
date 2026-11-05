"""Клавиатуры экранов шаблона. Примитивы (build_kb, «назад», пагинация) — в tgkit.kb."""

from aiogram.types import InlineKeyboardButton as Button
from aiogram.types import InlineKeyboardMarkup as Markup
from aiogram.utils.keyboard import InlineKeyboardBuilder as Builder
from tgkit.kb import build_kb, paginated_kb

from models.callbacks import NoteColorCB, NoteDeleteCB, NoteListCB, NoteViewCB, SettingsCB
from models.enums import NoteColor


def start_kb() -> Markup:
    return build_kb(("📝 Мои заметки", NoteListCB()), ("➕ Новая заметка", "note_new"))


def _note_row(note: dict) -> Button:
    icon = NoteColor(note["color"]).icon
    return Button(text=f"{icon} {note['title']}", callback_data=NoteViewCB(note_id=note["id"]).pack())


def notes_list_kb(notes: list[dict], page: int = 0, limit: int = 8) -> Markup:
    """Список заметок с пагинацией — типовой экран «много записей пользователя»."""
    kb, _ = paginated_kb(notes, page, limit, _note_row, lambda p: NoteListCB(page=p), empty_label="(Пока пусто)")
    kb.row(Button(text="➕ Новая заметка", callback_data="note_new"))
    kb.row(Button(text="⬅ В меню", callback_data="start_menu"))
    return kb.as_markup()


def note_view_kb(note_id: int, current: NoteColor) -> Markup:
    """Карточка заметки: смена метки + удаление."""
    kb = Builder()
    kb.row(
        *[
            Button(
                text=f"{color.icon}{' ·' if color is current else ''}",
                callback_data=NoteColorCB(note_id=note_id, color=color).pack(),
            )
            for color in NoteColor
        ]
    )
    kb.row(Button(text="🗑 Удалить", callback_data=NoteDeleteCB(note_id=note_id).pack()))
    kb.row(Button(text="⬅ К списку", callback_data=NoteListCB().pack()))
    return kb.as_markup()


def settings_kb(debug_enabled: bool) -> Markup:
    action = "disable" if debug_enabled else "enable"
    label = "🐞 DEBUG-логи: ВКЛ" if debug_enabled else "🐞 DEBUG-логи: выкл"
    return build_kb((label, SettingsCB(prop="debug", act=action)), ("⬅ В меню", "start_menu"))
