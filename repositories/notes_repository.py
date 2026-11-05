"""Демо-репозиторий. Главное здесь — не заметки, а ГРАНИЦА ВЛАДЕНИЯ.

`user_id` стоит в WHERE каждого запроса, включая чтение одной записи по id. Это не
перестраховка: `note_id` приходит из callback_data, а он подставляется свободно. Идентификаторы
последовательны (AUTOINCREMENT), так что перебор чужих — дело одной минуты.

Почему скоуп именно здесь, а не в мидлвари:
  * мидлварь не знает, какой ресурс к кому относится, без доменного запроса;
  * проверка ОДНОГО идентификатора создаёт ложное чувство защищённости — соседний
    уходит в SQL без скоупа, и дыра появляется там, где её не искали.

Правило простое: если в запросе есть чужой id, рядом обязан стоять user_id.
"""

from typing import Any

from models.enums import NoteColor

from db.database import Database


class NotesRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(self, user_id: int, title: str, body: str) -> int:
        return await self.db.execute_insert(
            "INSERT INTO notes (user_id, title, body) VALUES (?, ?, ?)",
            (user_id, title, body),
        )

    async def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        rows = await self.db.fetch_all(
            "SELECT id, title, color, created_at FROM notes WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
        return [dict(r) for r in rows]

    async def get(self, note_id: int, user_id: int) -> dict[str, Any] | None:
        """Чтение ОДНОЙ заметки — тоже со скоупом: иначе утечёт чужой текст."""
        row = await self.db.fetch_one(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        )
        return dict(row) if row else None

    async def set_color(self, note_id: int, user_id: int, color: NoteColor) -> int:
        return await self.db.execute(
            "UPDATE notes SET color = ? WHERE id = ? AND user_id = ?",
            (str(color), note_id, user_id),
        )

    async def delete(self, note_id: int, user_id: int) -> int:
        """Возвращает число удалённых строк: 0 означает «не ваша или не существует».

        Разницы между этими случаями пользователю знать не нужно — иначе по коду ответа
        можно перебором выяснить, какие id заняты.
        """
        return await self.db.execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        )

    async def count_for_user(self, user_id: int) -> int:
        row = await self.db.fetch_one("SELECT COUNT(*) AS n FROM notes WHERE user_id = ?", (user_id,))
        return int(row["n"]) if row else 0
