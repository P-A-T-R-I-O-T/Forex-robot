"""
Торговый движок для Forex Trading Bot.

Этот модуль содержит:
- Основной торговый цикл
- Выполнение стратегий
- Управление рисками
- Мониторинг сделок
- Отслеживание производительности
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import random

from loguru import logger
import numpy as np
import pandas as pd

from src.api.tinkoff_api import TinkoffAPI
from src.data.data_manager import DataManager
from src.models.portfolio import Portfolio
from src.models.trade import Trade
from src.models.strategy import StrategyResult
from src.strategies.base_strategy import BaseStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.breakout import BreakoutStrategy
from src.strategies.ml_strategy import MLStrategy
from src.utils.config import Config


class TradingEngine:
    """
    Основной торговый движок, который выполняет стратегии и управляет сделками.

    Атрибуты:
        config (Config): Конфигурация приложения
        api (TinkoffAPI): Обертка Tinkoff API
        data_manager (DataManager): Менеджер рыночных данных
        portfolio (Portfolio): Менеджер портфеля
        strategies (List[BaseStrategy]): Активные торговые стратегии
        active_trades (Dict[str, Trade]): Текущие открытые сделки
        trade_history (List[Trade]): Исторические сделки
        performance_metrics (Dict[str, float]): Отслеживание производительности
    """

    def __init__(
        self,
        config: Config,
        api: TinkoffAPI,
        data_manager: DataManager,
        portfolio: Portfolio,
    ):
        """
        Инициализация TradingEngine.

        Аргументы:
            config: Конфигурация приложения
            api: Обертка Tinkoff API
            data_manager: Менеджер рыночных данных
            portfolio: Менеджер портфеля
        """
        self.config = config
        self.api = api
        self.data_manager = data_manager
        self.portfolio = portfolio
        self.strategies: List[BaseStrategy] = []
        self.active_trades: Dict[str, Trade] = {}
        self.trade_history: List[Trade] = []
        self.performance_metrics: Dict[str, float] = {}
        self._running = False

    async def initialize(self):
        """Инициализация торгового движка."""
        logger.info("Инициализация TradingEngine")

        # Загрузка стратегий
        await self._load_strategies()

        # Загрузка исторических сделок
        self.trade_history = await self.data_manager.get_trade_history()

        logger.success("TradingEngine инициализирован")

    async def shutdown(self):
        """Завершение работы торгового движка."""
        logger.info("Завершение работы TradingEngine")
        self._running = False

        # Закрытие всех открытых сделок
        await self._close_all_trades()

        logger.success("TradingEngine завершил работу")

    async def run(self):
        """Основной торговый цикл."""
        self._running = True
        logger.info("Запуск основного цикла TradingEngine")

        try:
            while self._running:
                # Выполнение стратегий
                await self._execute_strategies()

                # Мониторинг открытых сделок
                await self._monitor_trades()

                # Обновление метрик производительности
                await self._update_performance()

                # Короткая пауза
                await asyncio.sleep(60)  # Запуск каждую минуту

        except Exception as e:
            logger.error(f"Ошибка в цикле TradingEngine: {e}")
            raise

    async def _load_strategies(self):
        """Загрузка и инициализация торговых стратегий."""
        logger.info("Загрузка торговых стратегий")

        # Стратегия возврата к среднему
        mean_reversion = MeanReversionStrategy(
            config=self.config,
            data_manager=self.data_manager,
        )
        await mean_reversion.initialize()
        self.strategies.append(mean_reversion)

        # Стратегия пробоя
        breakout = BreakoutStrategy(
            config=self.config,
            data_manager=self.data_manager,
        )
        await breakout.initialize()
        self.strategies.append(breakout)

        # Стратегия машинного обучения
        ml_strategy = MLStrategy(
            config=self.config,
            data_manager=self.data_manager,
        )
        await ml_strategy.initialize()
        self.strategies.append(ml_strategy)

        logger.info(f"Загружено {len(self.strategies)} торговых стратегий")

    async def _execute_strategies(self):
        """Выполнение всех активных торговых стратегий."""
        for strategy in self.strategies:
            try:
                # Получение сигналов от стратегии
                signals = await strategy.generate_signals()

                # Выполнение сделок на основе сигналов
                for signal in signals:
                    await self._process_signal(strategy, signal)

            except Exception as e:
                logger.error(f"Ошибка выполнения стратегии {strategy.name}: {e}")

    async def _process_signal(self, strategy: BaseStrategy, signal: StrategyResult):
        """
        Обработка торгового сигнала от стратегии.

        Аргументы:
            strategy: Стратегия, сгенерировавшая сигнал
            signal: Торговый сигнал для обработки
        """
        # Проверка наличия открытой сделки для этого инструмента
        if signal.figi in self.active_trades:
            logger.debug(f"Для {signal.figi} уже есть открытая сделка")
            return

        # Проверка лимитов риска портфеля
        if not await self.portfolio.check_risk_limits(signal.figi, signal.size):
            logger.debug(f"Превышены лимиты риска для {signal.figi}")
            return

        # Размещение ордера
        success, trade = await self.api.place_order(
            figi=signal.figi,
            direction=signal.direction,
            quantity=signal.size,
            order_type=signal.order_type,
            price=signal.price,
        )

        if success and trade:
            # Добавление в активные сделки
            self.active_trades[trade.figi] = trade

            # Запись стратегии, сгенерировавшей эту сделку
            trade.strategy = strategy.name
            trade.signal_strength = signal.strength

            # Сохранение в историю
            self.trade_history.append(trade)
            await self.data_manager.save_trade_result(trade)

            logger.info(
                f"Выполнена сделка {trade.direction} для {trade.figi} "
                f"по цене {trade.executed_price} (Стратегия: {strategy.name})"
            )

    async def _monitor_trades(self):
        """Мониторинг открытых сделок и управление выходами."""
        for figi, trade in list(self.active_trades.items()):
            try:
                # Проверка необходимости выхода из сделки
                exit_signal = await self._check_exit_conditions(trade)

                if exit_signal:
                    # Размещение ордера на выход
                    exit_direction = (
                        OrderDirection.ORDER_DIRECTION_SELL
                        if trade.direction == OrderDirection.ORDER_DIRECTION_BUY
                        else OrderDirection.ORDER_DIRECTION_BUY
                    )

                    success, exit_trade = await self.api.place_order(
                        figi=trade.figi,
                        direction=exit_direction,
                        quantity=trade.executed_quantity,
                    )

                    if success and exit_trade:
                        # Обновление сделки с информацией о выходе
                        trade.exit_price = exit_trade.executed_price
                        trade.exit_time = exit_trade.timestamp
                        trade.profit = (
                            (trade.exit_price - trade.executed_price) * trade.executed_quantity
                            if trade.direction == OrderDirection.ORDER_DIRECTION_BUY
                            else (trade.executed_price - trade.exit_price) * trade.executed_quantity
                        )
                        trade.status = "closed"

                        # Удаление из активных сделок
                        self.active_trades.pop(figi)

                        # Обновление сделки в истории
                        await self.data_manager.save_trade_result(trade)

                        logger.info(
                            f"Сделка для {trade.figi} закрыта с "
                            f"прибылью: {trade.profit:.2f}"
                        )

            except Exception as e:
                logger.error(f"Ошибка мониторинга сделки {trade.figi}: {e}")

    async def _check_exit_conditions(self, trade: Trade) -> bool:
        """
        Проверка условий выхода из сделки.

        Аргументы:
            trade: Сделка для проверки

        Возвращает:
            bool: True, если следует выйти из сделки
        """
        # Получение текущей цены
        prices = await self.api.get_current_prices([trade.figi])
        current_price = prices.get(trade.figi)

        if not current_price:
            return False

        # Расчет прибыли/убытка
        if trade.direction == OrderDirection.ORDER_DIRECTION_BUY:
            pl = (current_price - trade.executed_price) * trade.executed_quantity
        else:
            pl = (trade.executed_price - current_price) * trade.executed_quantity

        # Проверка стоп-лосса (2% от стоимости сделки)
        stop_loss = trade.executed_price * 0.02
        if (trade.direction == OrderDirection.ORDER_DIRECTION_BUY and
            current_price <= trade.executed_price - stop_loss):
            logger.info(f"Сработал стоп-лосс для {trade.figi}")
            return True

        if (trade.direction == OrderDirection.ORDER_DIRECTION_SELL and
            current_price >= trade.executed_price + stop_loss):
            logger.info(f"Сработал стоп-лосс для {trade.figi}")
            return True

        # Проверка тейк-профита (4% от стоимости сделки)
        take_profit = trade.executed_price * 0.04
        if (trade.direction == OrderDirection.ORDER_DIRECTION_BUY and
            current_price >= trade.executed_price + take_profit):
            logger.info(f"Сработал тейк-профит для {trade.figi}")
            return True

        if (trade.direction == OrderDirection.ORDER_DIRECTION_SELL and
            current_price <= trade.executed_price - take_profit):
            logger.info(f"Сработал тейк-профит для {trade.figi}")
            return True

        # Проверка выхода по времени (4 часа)
        if (datetime.utcnow() - trade.timestamp) > timedelta(hours=4):
            logger.info(f"Сработал выход по времени для {trade.figi}")
            return True

        return False

    async def _close_all_trades(self):
        """Закрытие всех открытых сделок."""
        for figi, trade in list(self.active_trades.items()):
            try:
                exit_direction = (
                    OrderDirection.ORDER_DIRECTION_SELL
                    if trade.direction == OrderDirection.ORDER_DIRECTION_BUY
                    else OrderDirection.ORDER_DIRECTION_BUY
                )

                success, exit_trade = await self.api.place_order(
                    figi=trade.figi,
                    direction=exit_direction,
                    quantity=trade.executed_quantity,
                )

                if success and exit_trade:
                    trade.exit_price = exit_trade.executed_price
                    trade.exit_time = exit_trade.timestamp
                    trade.profit = (
                        (trade.exit_price - trade.executed_price) * trade.executed_quantity
                        if trade.direction == OrderDirection.ORDER_DIRECTION_BUY
                        else (trade.executed_price - trade.exit_price) * trade.executed_quantity
                    )
                    trade.status = "closed"

                    self.active_trades.pop(figi)
                    await self.data_manager.save_trade_result(trade)

                    logger.info(
                        f"Сделка для {trade.figi} закрыта при завершении работы. "
                        f"Прибыль: {trade.profit:.2f}"
                    )

            except Exception as e:
                logger.error(f"Ошибка закрытия сделки {trade.figi}: {e}")

    async def _update_performance(self):
        """Обновление метрик производительности."""
        # Расчет общей прибыли/убытка
        total_pl = sum(t.profit for t in self.trade_history if hasattr(t, "profit"))

        # Расчет процента успешных сделок
        winning_trades = [t for t in self.trade_history if hasattr(t, "profit") and t.profit > 0]
        win_rate = len(winning_trades) / len(self.trade_history) if self.trade_history else 0

        # Расчет средней прибыли/убытка
        avg_pl = total_pl / len(self.trade_history) if self.trade_history else 0

        # Обновление метрик
        self.performance_metrics = {
            "total_profit_loss": total_pl,
            "win_rate": win_rate,
            "average_profit_loss": avg_pl,
            "total_trades": len(self.trade_history),
            "active_trades": len(self.active_trades),
        }

    async def get_performance_report(self) -> dict:
        """
        Получение отчета о производительности с ключевыми метриками.

        Возвращает:
            Словарь метрик производительности
        """
        return self.performance_metrics

    async def manual_trade(
        self,
        figi: str,
        direction: str,
        amount: float,
        order_type: str = "market",
        price: Optional[float] = None,
    ) -> Tuple[bool, Optional[Trade]]:
        """
        Выполнение ручной сделки (для тестирования).

        Аргументы:
            figi: FIGI инструмента
            direction: "buy" или "sell"
            amount: Сумма сделки в валюте
            order_type: "market" или "limit"
            price: Требуется для лимитных ордеров

        Возвращает:
            Кортеж (успех, Trade), где Trade содержит детали ордера
        """
        # Конвертация направления в OrderDirection
        order_direction = (
            OrderDirection.ORDER_DIRECTION_BUY
            if direction.lower() == "buy"
            else OrderDirection.ORDER_DIRECTION_SELL
        )

        # Конвертация типа ордера в OrderType
        order_type_enum = (
            OrderType.ORDER_TYPE_LIMIT
            if order_type.lower() == "limit"
            else OrderType.ORDER_TYPE_MARKET
        )

        # Получение текущей цены для расчета количества
        prices = await self.api.get_current_prices([figi])
        current_price = prices.get(figi, 1.0)  # По умолчанию 1.0, если цена недоступна

        quantity = int(amount / current_price)

        # Размещение ордера
        return await self.api.place_order(
            figi=figi,
            direction=order_direction,
            quantity=quantity,
            order_type=order_type_enum,
            price=price,
        )
