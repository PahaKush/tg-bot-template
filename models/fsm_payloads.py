import uuid
from typing import ClassVar

from pydantic import Field
from tgkit import FlowPayload


def new_flow_id() -> str:
    """Короткий идентификатор ОДНОГО запуска флоу.

    Нужен там, где у пользователя может оказаться две параллельно начатые операции: клик по
    клавиатуре первой не должен править контекст второй. Проверять «тот же пользователь» для
    этого недостаточно — он один и тот же.

    8 hex, а не полный uuid, из-за лимита Telegram в 64 байта на callback_data:
    tests/test_callback_access.py считает худший случай упаковки и не даст его превысить.
    """
    return uuid.uuid4().hex[:8]


class NoteCreationPayload(FlowPayload):
    """Контекст многошагового создания заметки.

    Каждый флоу хранится под своим flow_key, поэтому параллельные флоу не затирают друг
    друга в одном FSM-стейте.
    """

    flow_key: ClassVar[str] = "note_creation_flow"

    flow_id: str = Field(default_factory=new_flow_id)
    title: str | None = None
