import os
from pathlib import Path

import pytest
import pytest_asyncio

from repositories import NotesRepository, SettingsRepository, UserRepository
from services.notes_manager import NotesManager
from services.settings_manager import SettingsManager

from db.database import Database

# Тесты не должны зависеть от .env разработчика: ключ фиксируем явно.
os.environ.setdefault("DB_ENCRYPTION_KEY", "Tmtj_F7qT1D4J4Rk-QzTfBHgL0BvP9G2m1r5k4J9hA0=")


@pytest_asyncio.fixture()
async def db(tmp_path: Path):
    """Свежая БД на диске с применёнными миграциями, изолированная на каждый тест.

    Именно на диске, а не in-memory: у Database пул соединений, и :memory: дал бы каждому
    соединению СВОЮ пустую базу — тест проходил бы, а прод падал.
    """
    database = Database(str(tmp_path / "test.db"))
    await database.connect()
    await database.run_migrations()
    yield database
    await database.disconnect()


@pytest.fixture
def user_repo(db: Database) -> UserRepository:
    return UserRepository(db)


@pytest.fixture
def notes_repo(db: Database) -> NotesRepository:
    return NotesRepository(db)


@pytest.fixture
def settings_repo(db: Database) -> SettingsRepository:
    return SettingsRepository(db)


@pytest.fixture
def notes_manager(notes_repo: NotesRepository, db: Database) -> NotesManager:
    return NotesManager(notes_repo, db)


@pytest.fixture
def settings_manager(settings_repo: SettingsRepository, db: Database) -> SettingsManager:
    return SettingsManager(settings_repo, db)


@pytest_asyncio.fixture()
async def user(db: Database, user_repo: UserRepository) -> int:
    """Заведённый пользователь: notes.user_id — внешний ключ, без строки вставка упадёт."""
    async with db.transaction():
        await user_repo.add_user(1001, "tester", "Test User")
    return 1001


@pytest_asyncio.fixture()
async def other_user(db: Database, user_repo: UserRepository) -> int:
    async with db.transaction():
        await user_repo.add_user(2002, "stranger", "Stranger")
    return 2002
