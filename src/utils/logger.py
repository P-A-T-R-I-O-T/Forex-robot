# Настройка логирования

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from src.utils.config import Config


def setup_logger(name: str = 'trading-bot') -> logging.Logger:
    """Настройка системы логирования"""
    config = Config()

    logger = logging.getLogger(name)
    logger.setLevel(config.LOG_LEVEL)

    # Формат сообщений
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Консольный вывод
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Запись в файл (ротация по 5 МБ)
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        logs_dir / 'trading.log',
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger