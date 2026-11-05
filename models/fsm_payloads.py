from typing import ClassVar

from tgkit import FlowPayload


class NoteCreationPayload(FlowPayload):
    """Контекст многошагового создания заметки."""

    flow_key: ClassVar[str] = "note_creation_flow"

    title: str | None = None


class BroadcastPayload(FlowPayload):
    """Текст рассылки, ожидающий подтверждения."""

    flow_key: ClassVar[str] = "broadcast_flow"

    text: str
