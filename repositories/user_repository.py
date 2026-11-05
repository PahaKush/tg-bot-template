from typing import Any

from db.database import Database


class UserRepository:
    def __init__(self, db: Database):
        self.db = db

    async def add_user(self, user_id: int, username: str, full_name: str) -> None:
        """Upsert профиля. username может быть пустой строкой — при закрытых настройках
        приватности Telegram его не отдаёт, и это нормальное значение, а не ошибка."""
        await self.db.execute(
            """
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name
            """,
            (user_id, username, full_name),
        )

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT username, full_name FROM users WHERE user_id = ?", (user_id,))
        return dict(row) if row else None

    async def get_all_user_ids(self) -> list[int]:
        """Для рассылки. Отдаём только идентификаторы: тянуть профили незачем."""
        rows = await self.db.fetch_all("SELECT user_id FROM users")
        return [row["user_id"] for row in rows]

    async def count(self) -> int:
        row = await self.db.fetch_one("SELECT COUNT(*) AS n FROM users")
        return int(row["n"]) if row else 0
