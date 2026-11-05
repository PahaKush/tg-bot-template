from aiogram.fsm.state import State, StatesGroup


class AddNote(StatesGroup):
    """Многошаговый ввод: заголовок -> текст.

    Состояние отвечает только на вопрос «что мы сейчас ждём». Сами данные шага лежат в
    типизированном пейлоаде (models/fsm_payloads.py), а не разложены по ключам стейта:
    иначе каждый шаг заново угадывает, что положил предыдущий.
    """

    waiting_for_title = State()
    waiting_for_body = State()


class Broadcast(StatesGroup):
    waiting_for_text = State()
    confirming = State()
