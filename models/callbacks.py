from typing import ClassVar, Literal

from aiogram.filters.callback_data import CallbackData

from models.enums import Access, NoteColor


class NoteListCB(CallbackData, prefix="notes"):
    """Список заметок пользователя."""

    access: ClassVar[Access] = Access.USER
    page: int = 0


class NoteViewCB(CallbackData, prefix="note"):
    """Карточка заметки.

    note_id приходит от клиента и подставляется свободно — принадлежность проверяется
    НЕ здесь, а в SQL репозитория (`WHERE id = ? AND user_id = ?`). Проверять её в
    мидлвари означало бы дублировать доменное знание и всё равно упустить соседние id.
    """

    access: ClassVar[Access] = Access.USER
    note_id: int


class NoteColorCB(CallbackData, prefix="note_color"):
    """Смена метки заметки. Пример enum-поля в callback_data."""

    access: ClassVar[Access] = Access.USER
    note_id: int
    color: NoteColor


class NoteDeleteCB(CallbackData, prefix="note_del"):
    access: ClassVar[Access] = Access.USER
    note_id: int


class BroadcastSendCB(CallbackData, prefix="broadcast_send"):
    access: ClassVar[Access] = Access.ADMIN


class SettingsCB(CallbackData, prefix="settings"):
    """Переключатели настроек бота."""

    access: ClassVar[Access] = Access.ADMIN
    prop: Literal["debug"]
    act: Literal["enable", "disable"]
