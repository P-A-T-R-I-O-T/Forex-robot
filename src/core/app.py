"""
Основной модуль приложения Forex Trading Bot.

Этот модуль инициализирует и запускает торгового бота со всеми необходимыми компонентами:
- Подключения к API
- Обработка данных
- Выполнение стратегий
- Управление сделками
- Отчетность
"""

import asyncio
import logging
from loguru import logger
from typing import Optional
from pathlib import Path

from src.core.trading_engine import TradingEngine
from src.api.tinkoff_api import TinkoffAPI
from src.data.data_manager import DataManager
from src.models.portfolio import Portfolio
from src.utils.config import Config
from src.ui.cli import CLIInterface


class ForexTradingBot:
    """
    Основной класс приложения Forex Trading Bot.

    Атрибуты:
        config (Config): Конфигурация приложения
        api (TinkoffAPI): Обертка Tinkoff Invest API
        data_manager (DataManager): Управляет сбором и хранением рыночных данных
        trading_engine (TradingEngine): Выполняет торговые стратегии
        portfolio (Portfolio): Управляет портфелем и рисками
        cli (CLIInterface): Интерфейс командной строки
        running (bool): Флаг, указывающий на работу бота
    """

    def __init__(self):
        """Инициализация торгового бота со всеми компонентами."""
        self.config = Config()
        self.api: Optional[TinkoffAPI] = None
        self.data_manager: Optional[DataManager] = None
        self.trading_engine: Optional[TradingEngine] = None
        self.portfolio: Optional[Portfolio] = None
        self.cli: Optional[CLIInterface] = None
        self.running = False

    async def initialize(self):
        """Инициализация всех компонентов торгового бота."""
        logger.info("Инициализация Forex Trading Bot")

        # Загрузка конфигурации
        await self.config.load()

        # Инициализация подключения к API
        self.api = TinkoffAPI(self.config)
        await self.api.connect()

        # Инициализация менеджера данных
        self.data_manager = DataManager(self.config, self.api)
        await self.data_manager.initialize()

        # Инициализация менеджера портфеля
        self.portfolio = Portfolio(self.config, self.api)
        await self.portfolio.initialize()

        # Инициализация торгового движка
        self.trading_engine = TradingEngine(
            config=self.config,
            api=self.api,
            data_manager=self.data_manager,
            portfolio=self.portfolio
        )
        await self.trading_engine.initialize()

        # Инициализация CLI
        self.cli = CLIInterface(self)

        logger.success("Forex Trading Bot успешно инициализирован")

    async def run(self):
        """Запуск основного цикла торговли."""
        if not self.api or not self.data_manager or not self.trading_engine:
            raise RuntimeError("Компоненты не инициализированы. Сначала вызовите initialize().")

        self.running = True
        logger.info("Запуск основного цикла Forex Trading Bot")

        try:
            # Запуск сбора данных
            asyncio.create_task(self.data_manager.run())

            # Запуск торгового движка
            asyncio.create_task(self.trading_engine.run())

            # Запуск интерфейса командной строки
            await self.cli.run()

            # Поддержание работы бота
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Завершение работы Forex Trading Bot")
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Грациозное завершение работы торгового бота."""
        logger.info("Завершение работы компонентов Forex Trading Bot")
        self.running = False

        if self.trading_engine:
            await self.trading_engine.shutdown()

        if self.data_manager:
            await self.data_manager.shutdown()

        if self.api:
            await self.api.disconnect()

        logger.success("Forex Trading Bot успешно завершил работу")

    async def restart(self):
        """Перезапуск торгового бота."""
        logger.info("Перезапуск Forex Trading Bot")
        await self.shutdown()
        await self.initialize()
        await self.run()


async def main():
    """Точка входа в приложение Forex Trading Bot."""
    bot = ForexTradingBot()
    try:
        await bot.initialize()
        await bot.run()
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
