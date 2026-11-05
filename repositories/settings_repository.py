from db.database import Database


class SettingsRepository:
    def __init__(self, db: Database):
        self.db = db

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = await self.db.fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    async def get_log_level(self) -> str:
        return await self.get_setting("log_level", "INFO") or "INFO"

    async def set_log_level(self, log_level: str) -> None:
        await self.set_setting("log_level", log_level)
