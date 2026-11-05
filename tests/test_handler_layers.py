"""Структурные правила слоя хендлеров.

Три вещи, которые тихо расползаются, если их не держать:

1. Импорт внутри функции почти всегда прячет цикл импортов вместо того, чтобы развязать
   его, а часто цикла нет вовсе.
2. Приватное имя из соседнего модуля: правка в одном модуле молча меняет поведение
   другого. Общий код выносится в отдельный модуль публично.
3. Свой try/except вокруг safe_error_text: каждый такой блок заново решает, какую кнопку
   «назад» показать. Единственная точка — tgkit.utils.error_screen.
"""

import pathlib

from tgkit.testing import guards

HANDLERS_DIR = pathlib.Path(__file__).resolve().parent.parent / "handlers"


def test_no_function_level_imports():
    guards.assert_no_function_level_imports(HANDLERS_DIR)


def test_no_private_imports_between_handlers():
    guards.assert_no_private_imports_between_handlers(HANDLERS_DIR)


def test_error_screens_go_through_one_helper():
    guards.assert_error_screens_go_through_one_helper(HANDLERS_DIR)
