"""Каждый CallbackData обязан ЯВНО объявить, кто имеет право его нажать.

При неявном правиле (мидлварь включается, если у callback_data случайно окажется нужное
поле) новый коллбэк молча проходит без проверки — так появляется cross-tenant IDOR.
Здесь забыть разметку нельзя: падает этот тест, а не прод.
"""

import pytest
from tgkit.testing import guards

import models.callbacks as cb_module
from models.enums import Access

ALL_CALLBACKS = guards.collect_callbacks(cb_module)

# Разметка HANDLER означает «проверку делает сам хендлер». Это осознанный opt-out, и он
# должен оставаться редким и обозримым. Добавляя запись, убедитесь, что проверка в
# хендлере действительно есть, например:
#   "PickItemCB",  # id берётся из FSM-пейлоада, созданного проверенным путём
EXPECTED_HANDLER_CHECKED: set[str] = set()

# Предел каждого строкового поля callback_data. Без него худший случай упаковки не
# посчитать, поэтому новое строковое поле без записи здесь роняет тест.
STRING_FIELD_LIMITS: dict[str, int] = {}


def test_callbacks_discovered():
    assert ALL_CALLBACKS, "коллбэки не найдены — сломался импорт models.callbacks"


@pytest.mark.parametrize("klass", ALL_CALLBACKS, ids=lambda k: k.__name__)
def test_every_callback_declares_access(klass):
    guards.assert_every_callback_declares_access(klass, Access)


def test_handler_checked_set_is_exactly_as_expected():
    """Падает и когда HANDLER добавили новому коллбэку (проверьте хендлер), и когда его
    убрали (обновите список)."""
    actual = {k.__name__ for k in ALL_CALLBACKS if getattr(k, "access", None) is Access.HANDLER}
    assert actual == EXPECTED_HANDLER_CHECKED


@pytest.mark.parametrize("klass", ALL_CALLBACKS, ids=lambda k: k.__name__)
def test_callback_fits_telegram_limit(klass):
    """Telegram режет callback_data на 64 байтах, и поломка видна только на длинном значении."""
    guards.assert_callback_fits_telegram_limit(klass, STRING_FIELD_LIMITS)
