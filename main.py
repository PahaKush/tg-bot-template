"""Точка входа: сборка приложения и запуск polling.

`build_dispatcher()` вынесена из `main()` намеренно — так тесты собирают ТОТ ЖЕ диспетчер
с теми же мидлварями и порядком роутеров, а не свою упрощённую копию. Копия неизбежно
расходится с боевой сборкой, и тогда тесты проверяют не то, что работает.
"""

import asyncio
import contextlib
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import setup_dishka
from dotenv import load_dotenv
from tgkit import SQLiteStorage
from tgkit.middlewares import (
    AbandonedFlowMiddleware,
    AccessControlMiddleware,
    CallbackAnswerMiddleware,
    LoggingMiddleware,
    ThrottlingMiddleware,
    UserContextMiddleware,
    ValidCallbackMiddleware,
)

from core.di import AppProvider
from repositories import SettingsRepository, UserRepository
from services.crypto_service import CryptoService

from db.database import Database
from handlers import commands, errors, messages, notes

load_dotenv()


def admin_ids() -> list[int]:
    """ADMIN_IDS=111,222 из .env. Нечисловой мусор молча отбрасывается — опечатка в списке
    не должна ронять бота целиком, но и превращаться в «админ по умолчанию» тоже."""
    raw = os.getenv("ADMIN_IDS", "")
    return [int(part) for part in raw.replace(" ", "").split(",") if part.isdigit()]


def validate_environment() -> None:
    """Fail-fast на старте.

    Без токена бот всё равно не поедет, и узнать об этом лучше одной понятной строкой, а не
    необработанным исключением из недр polling.
    """
    if not os.getenv("BOT_TOKEN"):
        raise ValueError("BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните.")
    if not admin_ids():
        logging.warning("ADMIN_IDS пуст — админские команды недоступны никому.")
    CryptoService.validate_key()  # ключ опционален, но БИТЫЙ обязан ронять старт


def build_dispatcher(container: AsyncContainer, admins: list[int], storage: BaseStorage | None = None) -> Dispatcher:
    """Собирает Dispatcher. Порядок мидлварей и роутеров важен — см. комментарии."""
    dp = Dispatcher(storage=storage or SQLiteStorage(), admins=admins)

    setup_dishka(container=container, router=dp, auto_inject=True)

    # Самая внешняя на callback: гасит «часики» даже если мидлварь ниже отбросит апдейт.
    dp.callback_query.outer_middleware(CallbackAnswerMiddleware())

    dp.update.middleware(LoggingMiddleware())

    # Троттлинг раньше остальных — отсекает спам до походов в БД.
    # ОДИН инстанс на message и callback: иначе клик и сообщение за <0.5 с проходят оба
    # и конкурентно правят FSM.
    throttling = ThrottlingMiddleware(default_rate_limit=0.5)
    dp.message.middleware(throttling)
    dp.callback_query.middleware(throttling)

    # Каркас не знает репозиториев приложения: ему передаются классы, зарегистрированные в dishka.
    user_context = UserContextMiddleware(store_type=UserRepository, db_type=Database)
    dp.message.middleware(user_context)
    dp.callback_query.middleware(user_context)
    dp.callback_query.middleware(ValidCallbackMiddleware())
    # resolver не нужен: владение заметкой проверяется в SQL (NotesRepository), а не здесь.
    dp.callback_query.middleware(AccessControlMiddleware())

    # Последней: «Отмена» и любая другая навигация закрывают брошенный сценарий ввода.
    # Без неё после «Отмены» в мастере заметки следующий текст стал бы заголовком.
    # Стоит после проверки доступа: отказ в доступе не должен рвать чужой ввод.
    abandoned_flow = AbandonedFlowMiddleware()
    dp.callback_query.middleware(abandoned_flow)
    dp.message.middleware(abandoned_flow)

    # errors — последним: в нём catch-all на несовпавшие callback'и.
    dp.include_routers(commands.router, notes.router, messages.router, errors.router)
    return dp


async def setup_commands(bot: Bot, admins: list[int]) -> None:
    """Разные наборы команд: обычным — только /start, админам — полный."""
    await bot.set_my_commands([BotCommand(command="start", description="Меню")], scope=BotCommandScopeDefault())

    admin_commands = [
        BotCommand(command="start", description="Меню"),
        BotCommand(command="stats", description="Статистика 📊"),
        BotCommand(command="settings", description="Настройки ⚙️"),
        BotCommand(command="broadcast", description="Рассылка 📢"),
    ]
    for admin_id in admins:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.warning("Не удалось установить команды для %s: %s", admin_id, e)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    validate_environment()

    container = make_async_container(AppProvider())

    # Подключение и миграции — явно и до старта polling. Контейнер отдаёт тот же синглтон
    # Database, поэтому дальше все репозитории работают с уже готовым пулом соединений.
    db = await container.get(Database)
    await db.connect()
    await db.run_migrations()

    settings_repo = await container.get(SettingsRepository)
    level = await settings_repo.get_log_level()
    logging.getLogger().setLevel(level)
    logging.info("Уровень логирования: %s", level)

    admins = admin_ids()
    dp = build_dispatcher(container, admins)
    bot = Bot(token=os.environ["BOT_TOKEN"], default=DefaultBotProperties(parse_mode="HTML"))

    await setup_commands(bot, admins)

    async def on_shutdown(*_args: object, **_kwargs: object) -> None:
        logging.info("Остановка бота...")
        await dp.storage.close()
        await db.disconnect()
        await container.close()

    dp.shutdown.register(on_shutdown)

    logging.info("Бот запущен.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
