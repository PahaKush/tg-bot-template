"""Служебный CLI: инициализация БД и генерация ключа шифрования.

Отдельная точка входа нужна, чтобы разовые операции не приходилось делать «через бота»
или руками в sqlite: их надо выполнять до первого запуска.
"""

import asyncio

import typer

from services.crypto_service import CryptoService

from db.database import Database

app = typer.Typer(help="Утилиты обслуживания бота.")


@app.command()
def initdb(path: str = "db_data/app.db") -> None:
    """Создаёт БД и применяет миграции."""

    async def _run() -> None:
        db = Database(path)
        await db.connect()
        await db.run_migrations()
        await db.disconnect()

    asyncio.run(_run())
    typer.echo(f"✅ База готова: {path}")


@app.command()
def genkey() -> None:
    """Генерирует Fernet-ключ для DB_ENCRYPTION_KEY."""
    typer.echo(CryptoService.generate_key())


if __name__ == "__main__":
    app()
