# Загрузка конфигурации


import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional


class Config:
    """Класс для работы с конфигурацией приложения"""

    def __init__(self):
        load_dotenv(Path(__file__).parent.parent / '.env')

        self.TOKEN: str = self._get_env('TINKOFF_TOKEN')
        self.ACCOUNT_ID: str = self._get_env('ACCOUNT_ID')
        self.REPORTS_DIR: Path = Path(self._get_env('REPORTS_DIR', 'reports'))
        self.LOG_LEVEL: str = self._get_env('LOG_LEVEL', 'INFO')

    def _get_env(self, key: str, default: Optional[str] = None) -> str:
        """Получение переменной окружения"""
        value = os.getenv(key, default)
        if value is None:
            raise ValueError(f"Не задана обязательная переменная окружения: {key}")
        return value

    def validate(self):
        """Валидация конфигурации"""
        required = [self.TOKEN, self.ACCOUNT_ID]
        if not all(required):
            raise ValueError("Не все обязательные параметры конфигурации заданы")