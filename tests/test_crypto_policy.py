"""Шифрование полей в шаблоне идёт по ЕГО политике: ключ необязателен.

Шаблон обязан подниматься «из коробки», без DB_ENCRYPTION_KEY, а строки, записанные
до включения ключа, читаться как есть. Базовая политика tgkit строгая (без ключа —
ValueError, на старой открытой строке — InvalidToken), поэтому обёртки шаблона передают
свою.
"""

from typing import ClassVar

import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel

from services.crypto_service import CryptoService, decrypt_fields, encrypt_fields


class Secret(BaseModel):
    secret_fields: ClassVar[tuple[str, ...]] = ("value",)
    value: str


@pytest.fixture(autouse=True)
def _reset_cipher():
    CryptoService.reset()
    yield
    CryptoService.reset()


def test_works_without_key(monkeypatch):
    monkeypatch.delenv("DB_ENCRYPTION_KEY", raising=False)

    assert encrypt_fields(Secret(value="v")).value == "v"
    assert decrypt_fields(Secret(value="v")).value == "v"


def test_reads_plaintext_written_before_the_key(monkeypatch):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", Fernet.generate_key().decode())

    assert decrypt_fields(Secret(value="old-plaintext")).value == "old-plaintext"


def test_encrypts_when_key_is_set(monkeypatch):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", Fernet.generate_key().decode())

    sealed = encrypt_fields(Secret(value="v"))

    assert sealed.value != "v"
    assert decrypt_fields(sealed).value == "v"
