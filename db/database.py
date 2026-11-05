"""Доступ к SQLite — тонкая обёртка над каркасом.

Сам Database (пул на чтение, запись только внутри transaction(), guard от мутаций
в fetch_*) живёт в tgkit.db.database. Здесь к нему привязываются путь БД этого
проекта и его реестр миграций, чтобы вызывающему коду было достаточно `Database()`.
"""

from tgkit.db.database import Database as _KitDatabase

from db.migrations import MIGRATIONS

DB_PATH = "db_data/app.db"


class Database(_KitDatabase):
    def __init__(self, db_path: str = DB_PATH, read_pool_size: int = 4) -> None:
        super().__init__(db_path=db_path, read_pool_size=read_pool_size, migrations=MIGRATIONS)


__all__ = ["DB_PATH", "Database"]
