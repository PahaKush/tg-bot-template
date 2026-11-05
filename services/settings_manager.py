import logging

from repositories import SettingsRepository

from db.database import Database


class SettingsManager:
    def __init__(self, settings_repo: SettingsRepository, db: Database):
        self.settings_repo = settings_repo
        self.db = db

    async def toggle_setting(self, setting_type: str, action: str) -> bool:
        """Атомарно меняет настройку и возвращает новое состояние."""
        async with self.db.transaction():
            if setting_type == "debug":
                new_level = "DEBUG" if action == "enable" else "INFO"
                await self.settings_repo.set_log_level(new_level)

                # Сайд-эффект инкапсулирован в бизнес-логике
                logging.getLogger().setLevel(new_level)

            # Сразу читаем свежий статус в той же транзакции (read-your-writes)
            log_level = await self.settings_repo.get_log_level()

        return log_level == "DEBUG"
