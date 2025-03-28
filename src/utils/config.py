# Загрузка конфигурации


from dotenv import load_dotenv
import os
from pathlib import Path
from typing import Optional

# Загрузка переменных окружения
load_dotenv(Path(__file__).parent.parent.parent / '.env')

class Config:
    """Класс для работы с конфигурацией приложения"""

    def __init__(self):
        self.TOKEN = self._get_required_env('TINKOFF_TOKEN')
        self.ACCOUNT_ID = self._get_required_env('ACCOUNT_ID')
        self.REPORTS_DIR = self._get_path_env('REPORTS_DIR', 'reports')
        self.LOG_LEVEL = self._get_optional_env('LOG_LEVEL', 'INFO').upper()

    def _get_required_env(self, key: str) -> str:
        """Получение обязательной переменной окружения"""
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Обязательная переменная {key} не найдена в .env")
        return value

    def _get_optional_env(self, key: str, default: str) -> str:
        """Получение необязательной переменной с дефолтным значением"""
        return os.getenv(key, default)

    def _get_path_env(self, key: str, default: str) -> Path:
        """Получение и создание пути из переменной окружения"""
        path = Path(self._get_optional_env(key, default))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_valid(self) -> bool:
        """Проверка валидности конфигурации"""
        return all([self.TOKEN, self.ACCOUNT_ID])

    def __repr__(self) -> str:
        return (f"Config(TOKEN=***, ACCOUNT_ID={self.ACCOUNT_ID}, "
                f"REPORTS_DIR={self.REPORTS_DIR}, LOG_LEVEL={self.LOG_LEVEL})")