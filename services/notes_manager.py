"""Тонкий сервисный слой над репозиторием.

Зачем он вообще нужен, если репозиторий уже есть: сервис владеет ТРАНЗАКЦИЕЙ и правилами,
репозиторий — только SQL. Как только операция перестаёт быть одним запросом (создать +
списать квоту + записать в журнал), это должно быть одно атомарное место, и оно уже есть.

Здесь же живут доменные проверки, чей результат — понятная пользователю ошибка (AppError),
а не молчаливый отказ.
"""

from typing import Any

from tgkit import NotFoundError, UserInputError

from repositories import NotesRepository

from models.enums import NoteColor

from db.database import Database

MAX_NOTES_PER_USER = 50
MAX_TITLE_LEN = 64
# Карточка — заголовок, дата и текст в одном сообщении, а у Telegram лимит 4096 символов.
MAX_BODY_LEN = 4000


def clean_title(text: str | None) -> str:
    title = (text or "").strip()
    if not title:
        raise UserInputError("Нужен текст заголовка.")
    if len(title) > MAX_TITLE_LEN:
        raise UserInputError(f"Заголовок длиннее {MAX_TITLE_LEN} символов — пришлите короче.")
    return title


def clean_body(text: str | None) -> str:
    body = (text or "").strip()
    if not body:
        raise UserInputError("Нужен текст заметки.")
    if len(body) > MAX_BODY_LEN:
        raise UserInputError(f"Текст длиннее {MAX_BODY_LEN} символов — пришлите короче.")
    return body


class NotesManager:
    def __init__(self, notes_repo: NotesRepository, db: Database):
        self.notes_repo = notes_repo
        self.db = db

    async def add_note(self, user_id: int, title: str, body: str) -> int:
        title, body = clean_title(title), clean_body(body)

        async with self.db.transaction():
            # Проверка и вставка в ОДНОЙ транзакции: иначе два быстрых сообщения подряд
            # пройдут лимит оба (классический TOCTOU на счётчике).
            if await self.notes_repo.count_for_user(user_id) >= MAX_NOTES_PER_USER:
                raise UserInputError(f"Достигнут лимит в {MAX_NOTES_PER_USER} заметок.")
            return await self.notes_repo.create(user_id, title, body)

    async def get_note(self, note_id: int, user_id: int) -> dict[str, Any]:
        note = await self.notes_repo.get(note_id, user_id)
        if note is None:
            # Одинаковый ответ и для «нет такой», и для «чужая»: иначе по разнице ответов
            # перебором выясняется, какие id существуют.
            raise NotFoundError("Заметка не найдена.")
        return note

    async def set_color(self, note_id: int, user_id: int, color: NoteColor) -> None:
        async with self.db.transaction():
            if not await self.notes_repo.set_color(note_id, user_id, color):
                raise NotFoundError("Заметка не найдена.")

    async def delete_note(self, note_id: int, user_id: int) -> None:
        async with self.db.transaction():
            if not await self.notes_repo.delete(note_id, user_id):
                raise NotFoundError("Заметка не найдена.")
