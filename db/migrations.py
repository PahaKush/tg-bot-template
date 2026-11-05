"""Миграции схемы. Раннер — в tgkit.db.migrations, здесь только список.

Каждая запись — {"version": int, "name": str} плюс "sql" и/или "python_func".
python_func нужен там, где SQL не хватает: пересчёт данных, условный ALTER, шифрование
существующих строк. Раннер применяет только недостающие версии и пишет номер в той же
транзакции, что и миграцию. Для "sql" это не спасает от наполовину применённого скрипта
(executescript коммитит сам), поэтому SQL-миграции пишутся идемпотентными.
"""

from tgkit import Migration

MIGRATIONS: list[Migration] = [
    {
        "version": 1,
        "name": "baseline",
        "sql": """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Демо-сущность. Обратите внимание на user_id: он есть в КАЖДОМ запросе
            -- репозитория — это и есть граница владения (см. NotesRepository).
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT 'default',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id);

            INSERT OR IGNORE INTO settings (key, value) VALUES ('log_level', 'INFO');
        """,
    }
]


# Пример миграции на Python — раскомментируйте как образец, когда SQL станет мало.
#
# async def _backfill_something(conn: aiosqlite.Connection) -> None:
#     cur = await conn.execute("PRAGMA table_info(notes)")
#     cols = {row["name"] for row in await cur.fetchall()}
#     if "pinned" not in cols:
#         await conn.execute("ALTER TABLE notes ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
#
# MIGRATIONS.append({"version": 2, "name": "notes_pinned", "python_func": _backfill_something})


__all__ = ["MIGRATIONS"]
