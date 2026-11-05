"""Сквозной прогон флоу через НАСТОЯЩИЙ Dispatcher.

Зачем это отдельно от юнит-тестов: половина интересного живёт не в хендлерах, а вокруг них —
в мидлварях (разметка доступа, контекст пользователя), в порядке роутеров (catch-all на
устаревшие кнопки) и в самом факте, что aiogram сумел разобрать callback_data. Прямой вызов
хендлера всё это проходит мимо и потому подтверждает меньше, чем кажется.

Подменяется ТОЛЬКО транспорт до Telegram: сессия записывает вызовы вместо отправки. Всё
остальное настоящее — сборка из `build_dispatcher()`, реальный DI-контейнер, реальная
SQLite-схема с миграциями.

Тот же приём ловит вещи, которые юнит-тестами не видны: например, попытку отредактировать
сообщение, которое Telegram редактировать не даёт.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, Update, User
from dishka import make_async_container

from core.di import AppProvider

from db.database import Database
from main import build_dispatcher

FAKE_TOKEN = "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
USER_ID = 4242


@dataclass
class Sent:
    method: str
    text: str = ""
    markup: InlineKeyboardMarkup | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def buttons(self) -> list[tuple[str, str]]:
        rows = getattr(self.markup, "inline_keyboard", None) or []
        return [(b.text, b.callback_data or "") for row in rows for b in row]

    def find(self, needle: str) -> str | None:
        """callback_data первой кнопки, чья подпись содержит needle."""
        return next((data for text, data in self.buttons() if needle.lower() in text.lower()), None)


class RecordingSession(BaseSession):
    """Записывает вызовы Bot API вместо отправки и возвращает правдоподобные ответы."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[Sent] = []
        self._msg_id = 1000

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):
        yield b""

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:
        data = method.model_dump(exclude_none=True)
        name = type(method).__name__
        markup = getattr(method, "reply_markup", None)
        self.sent.append(Sent(name, str(data.get("text") or ""), markup, data))

        if name in ("SendMessage", "EditMessageText"):
            self._msg_id += 1
            return Message(
                message_id=self._msg_id,
                date=0,
                chat=Chat(id=USER_ID, type="private"),
                text=str(data.get("text") or " "),
                reply_markup=markup if isinstance(markup, InlineKeyboardMarkup) else None,
            ).as_(bot)
        if name == "GetMe":
            return User(id=1, is_bot=True, first_name="Bot", username="test_bot").as_(bot)
        return True


class Harness:
    def __init__(self, dp: Dispatcher, bot: Bot, session: RecordingSession):
        self.dp, self.bot, self.session = dp, bot, session
        self._update_id = 0

    def _user(self) -> User:
        return User(id=USER_ID, is_bot=False, first_name="Tester", username="tester")

    async def _feed(self, update: Update) -> list[Sent]:
        before = len(self.session.sent)
        # Троттлинг отсекает синтетические апдейты, идущие за миллисекунды: окно 0.5 с на
        # пользователя. Сбрасываем его, иначе падают проверки, к троттлингу отношения не имеющие.
        for observer in (self.dp.message, self.dp.callback_query):
            for mw in observer.middleware:
                if hasattr(mw, "users"):
                    mw.users.clear()
        await self.dp.feed_update(self.bot, update)
        return self.session.sent[before:]

    async def send(self, text: str) -> list[Sent]:
        self._update_id += 1
        return await self._feed(
            Update(
                update_id=self._update_id,
                message=Message(
                    message_id=self._update_id,
                    date=0,
                    chat=Chat(id=USER_ID, type="private"),
                    from_user=self._user(),
                    text=text,
                ),
            )
        )

    async def click(self, data: str) -> list[Sent]:
        self._update_id += 1
        return await self._feed(
            Update(
                update_id=self._update_id,
                callback_query=CallbackQuery(
                    id=f"cb{self._update_id}",
                    from_user=self._user(),
                    chat_instance="ci",
                    data=data,
                    message=Message(
                        message_id=self._update_id,
                        date=0,
                        chat=Chat(id=USER_ID, type="private"),
                        text="prev",
                    ),
                ),
            )
        )

    @staticmethod
    def texts(batch: list[Sent]) -> str:
        return "\n".join(s.text for s in batch if s.text)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def _app(tmp_path_factory):
    """Диспетчер собирается ОДИН раз на модуль.

    Роутеры в aiogram — модульные синглтоны, и router нельзя подключить ко второму
    Dispatcher: `RuntimeError: Router is already attached`. Поэтому фикстура модульная, а
    изоляция тестов достигается очисткой таблиц (см. `harness`), а не пересборкой.
    """
    container = make_async_container(AppProvider())
    db = await container.get(Database)
    db._db_path = tmp_path_factory.mktemp("e2e") / "e2e.db"
    await db.connect()
    await db.run_migrations()

    session = RecordingSession()
    bot = Bot(token=FAKE_TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    dp = build_dispatcher(container, admins=[USER_ID], storage=MemoryStorage())
    # dishka с auto_inject патчит хендлеры не сразу, а startup-хуком: без emit_startup
    # все FromDishka-параметры окажутся пустыми и хендлеры упадут на отсутствии аргумента.
    await dp.emit_startup(bot=bot)

    yield dp, bot, session, db

    await db.disconnect()
    await container.close()


@pytest_asyncio.fixture(loop_scope="module")
async def harness(_app):
    dp, bot, session, db = _app

    async with db.transaction():
        await db.execute("DELETE FROM notes")
        await db.execute("DELETE FROM users")
    session.sent.clear()
    await dp.storage.close()
    dp.workflow_data["admins"] = [USER_ID]

    return Harness(dp, bot, session)


@pytest.mark.asyncio(loop_scope="module")
async def test_start_shows_menu(harness: Harness):
    out = await harness.send("/start")

    assert "Привет" in harness.texts(out)
    assert any("заметк" in text.lower() for msg in out for text, _ in msg.buttons())


@pytest.mark.asyncio(loop_scope="module")
async def test_full_note_flow(harness: Harness):
    """Создание заметки целиком: кнопка -> заголовок -> текст -> список -> карточка."""
    await harness.send("/start")

    out = await harness.click("note_new")
    assert "заголовок" in harness.texts(out).lower()

    out = await harness.send("Купить молоко")
    assert "текст" in harness.texts(out).lower()

    out = await harness.send("Два литра")
    assert "сохранена" in harness.texts(out).lower()

    out = await harness.click("notes:0")
    assert "Ваши заметки:</b> 1" in harness.texts(out)

    note_cb = next((m.find("Купить") for m in out if m.find("Купить")), None)
    assert note_cb, "заметка не появилась в списке"

    out = await harness.click(note_cb)
    assert "Два литра" in harness.texts(out)


@pytest.mark.asyncio(loop_scope="module")
async def test_unmarked_callback_is_rejected(harness: Harness):
    """Кнопка из устаревшего меню обязана получить ответ, а не оставить «часики»."""
    out = await harness.click("totally_unknown_callback")

    assert any(s.method == "AnswerCallbackQuery" for s in out), "callback остался без ответа"


@pytest.mark.asyncio(loop_scope="module")
async def test_admin_only_callback_denied_for_stranger(harness: Harness):
    """Разметка Access.ADMIN должна отсекать в мидлвари, а не в хендлере."""
    harness.dp.workflow_data["admins"] = []  # тот же пользователь, но больше не админ

    out = await harness.click("settings:debug:enable")

    assert "прав" in harness.texts(out).lower() or any("прав" in str(s.raw.get("text", "")).lower() for s in out)


@pytest.mark.asyncio(loop_scope="module")
async def test_cancel_ends_note_flow(harness: Harness):
    """«Отмена» в мастере заметки закрывает сценарий: следующий текст — не заголовок.

    Кнопка «Отмена ❌» ведёт на обычный экран списка (NoteListCB), который состояние не
    трогает. Без AbandonedFlowMiddleware бот остался бы в AddNote.waiting_for_title, и
    первое же сообщение молча начало бы заметку.
    """
    await harness.send("/start")
    await harness.click("note_new")

    out = await harness.click("notes:0")  # «Отмена ❌»
    assert "Ваши заметки:</b> 0" in harness.texts(out)

    out = await harness.send("Купить молоко")
    assert "Не понял" in harness.texts(out)
    assert "текст заметки" not in harness.texts(out).lower()

    out = await harness.click("notes:0")
    assert "Ваши заметки:</b> 0" in harness.texts(out)  # заметка так и не появилась


@pytest.mark.asyncio(loop_scope="module")
async def test_stale_button_does_not_break_note_flow(harness: Harness):
    """Мёртвая кнопка из старого сообщения отвечает «меню устарело», но ввод не рвёт."""
    await harness.send("/start")
    await harness.click("note_new")

    await harness.click("totally_unknown_callback")
    out = await harness.send("Купить молоко")

    assert "текст заметки" in harness.texts(out).lower()


@pytest.mark.asyncio(loop_scope="module")
async def test_broadcast_sends_escaped_html(harness: Harness):
    """Бот шлёт с parse_mode=HTML: сырой «<» Telegram отверг бы у каждого получателя."""
    await harness.send("/broadcast")
    out = await harness.send("Цена < 100")

    sent = [s.text for s in out if s.method == "SendMessage" and "Цена" in s.text]
    assert sent == ["Цена &lt; 100"]
