"""Шифрование чувствительных полей в покое — политика этого шаблона.

Операции живут в tgkit.crypto. Здесь задаётся политика: шифрование ОПЦИОНАЛЬНО,
чтобы шаблон поднимался «из коробки», а включение было осознанным шагом.

ВАЖНО: включать шифрование нужно ДО первой записи. Если в БД уже лежат открытые
данные, после включения ключа decrypt вернёт их как есть (tolerate_plaintext), но
зашифровать их задним числом придётся отдельной миграцией.

Если без ключа приложение бесполезно (например, хранит токены доступа к серверам),
политика обратная: required = True и tolerate_plaintext = False — там InvalidToken
означает «не тот ключ», и молчать об этом нельзя.

encrypt_fields/decrypt_fields здесь — обёртки с политикой шаблона: tgkit требует
передавать политику явно, а обёртки избавляют от этого каждый вызов.
"""

from tgkit.crypto import CryptoService as _KitCryptoService
from tgkit.crypto import HasSecretFields
from tgkit.crypto import decrypt_fields as _decrypt_fields
from tgkit.crypto import encrypt_fields as _encrypt_fields


class CryptoService(_KitCryptoService):
    required = False
    tolerate_plaintext = True


def encrypt_fields[T: HasSecretFields](model: T) -> T:
    """Шифрует secret_fields модели по политике шаблона (без ключа — как есть)."""
    return _encrypt_fields(model, crypto=CryptoService)


def decrypt_fields[T: HasSecretFields](model: T) -> T:
    """Расшифровывает по политике шаблона: строка, записанная до ключа, отдаётся как есть."""
    return _decrypt_fields(model, crypto=CryptoService)


__all__ = ["CryptoService", "decrypt_fields", "encrypt_fields"]
