"""Граница владения: чужой ресурс недоступен ни на чтение, ни на изменение.

Это главный тест шаблона. Идентификаторы в callback_data приходят от клиента и
последовательны (AUTOINCREMENT), поэтому перебор чужих — дело одной минуты. Единственная
надёжная защита — скоуп по user_id в SQL КАЖДОГО запроса; здесь он и проверяется.

Копируйте этот файл вместе с фичей: у любой сущности, принадлежащей пользователю, должен
быть такой же набор проверок.
"""

import pytest
from tgkit import NotFoundError, UserInputError

from repositories import NotesRepository
from services.notes_manager import MAX_NOTES_PER_USER, NotesManager

from models.enums import NoteColor


@pytest.mark.asyncio
async def test_owner_sees_own_note(notes_manager: NotesManager, user: int):
    note_id = await notes_manager.add_note(user, "Заголовок", "Текст")

    note = await notes_manager.get_note(note_id, user)

    assert note["title"] == "Заголовок"


@pytest.mark.asyncio
async def test_stranger_cannot_read_foreign_note(notes_manager: NotesManager, user: int, other_user: int):
    """Чужая заметка неотличима от несуществующей — иначе по разнице ответов перебором
    выясняется, какие id заняты."""
    note_id = await notes_manager.add_note(user, "Секрет", "Тело")

    with pytest.raises(NotFoundError):
        await notes_manager.get_note(note_id, other_user)


@pytest.mark.asyncio
async def test_stranger_cannot_delete_foreign_note(
    notes_manager: NotesManager, notes_repo: NotesRepository, user: int, other_user: int
):
    note_id = await notes_manager.add_note(user, "Секрет", "Тело")

    with pytest.raises(NotFoundError):
        await notes_manager.delete_note(note_id, other_user)

    assert await notes_repo.get(note_id, user) is not None  # на месте


@pytest.mark.asyncio
async def test_stranger_cannot_modify_foreign_note(
    notes_manager: NotesManager, notes_repo: NotesRepository, user: int, other_user: int
):
    note_id = await notes_manager.add_note(user, "Секрет", "Тело")

    with pytest.raises(NotFoundError):
        await notes_manager.set_color(note_id, other_user, NoteColor.DONE)

    assert (await notes_repo.get(note_id, user))["color"] == "default"


@pytest.mark.asyncio
async def test_list_is_scoped_to_owner(notes_manager: NotesManager, notes_repo: NotesRepository, user, other_user):
    await notes_manager.add_note(user, "Моя", "…")
    await notes_manager.add_note(other_user, "Чужая", "…")

    titles = [n["title"] for n in await notes_repo.list_for_user(user)]

    assert titles == ["Моя"]


@pytest.mark.asyncio
async def test_owner_can_manage_own_note(notes_manager: NotesManager, notes_repo: NotesRepository, user: int):
    """Скоуп не должен ломать легитимный путь — иначе «защита» просто выключает фичу."""
    note_id = await notes_manager.add_note(user, "Моя", "Тело")

    await notes_manager.set_color(note_id, user, NoteColor.IMPORTANT)
    assert (await notes_repo.get(note_id, user))["color"] == "important"

    await notes_manager.delete_note(note_id, user)
    assert await notes_repo.get(note_id, user) is None


@pytest.mark.asyncio
async def test_limit_is_enforced_inside_transaction(notes_manager: NotesManager, user: int):
    """Проверка лимита и вставка — в одной транзакции, иначе два быстрых сообщения
    подряд проходят лимит оба (TOCTOU на счётчике)."""
    for i in range(MAX_NOTES_PER_USER):
        await notes_manager.add_note(user, f"№{i}", "…")

    with pytest.raises(UserInputError, match="лимит"):
        await notes_manager.add_note(user, "Лишняя", "…")
