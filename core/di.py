"""Проводка зависимостей (dishka).

Один провайдер на всё приложение. Хендлеры объявляют, что им нужно, аннотацией
`FromDishka[X]` — и не знают ни как X собран, ни от чего он зависит. Добавление
зависимости в конструктор сервиса не трогает ни один хендлер.

Scope.APP: все объекты — синглтоны на время жизни процесса. Состояния они не держат,
а Database внутри сам управляет пулом соединений.
"""

from dishka import Provider, Scope, provide

from repositories import NotesRepository, SettingsRepository, UserRepository
from services.notes_manager import NotesManager
from services.settings_manager import SettingsManager

from db.database import Database


class AppProvider(Provider):
    scope = Scope.APP

    @provide
    def get_database(self) -> Database:
        # Подключение и миграции выполняются явно в main.py при старте.
        return Database()

    # Репозитории: только SQL, без бизнес-правил.
    user_repo = provide(UserRepository)
    settings_repo = provide(SettingsRepository)
    notes_repo = provide(NotesRepository)

    # Сервисы: транзакции и доменные правила. Зависимости внедряются по типам конструктора.
    settings_manager = provide(SettingsManager)
    notes_manager = provide(NotesManager)
