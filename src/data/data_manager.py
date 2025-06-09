"""
Менеджер данных для Forex Trading Bot.

Этот модуль обрабатывает:
- Сбор и хранение рыночных данных
- Управление историческими данными
- Потоковую передачу данных в реальном времени
- Предварительную обработку данных и feature engineering
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from pathlib import Path

import pandas as pd
from loguru import logger

from src.api.tinkoff_api import TinkoffAPI
from src.utils.config import Config
from src.data.schemas import CandleData, IndicatorData
from src.data.database import DatabaseManager


class DataManager:
    """
    Управляет всеми операциями с данными для торгового бота.

    Атрибуты:
        config (Config): Конфигурация приложения
        api (TinkoffAPI): Обертка Tinkoff API
        db (DatabaseManager): Интерфейс базы данных
        historical_data (Dict[str, pd.DataFrame]): Кэшированные исторические данные
        realtime_data (Dict[str, List[CandleData]]): Буферы данных в реальном времени
        indicators (Dict[str, Dict[str, IndicatorData]]): Рассчитанные индикаторы
    """

    def __init__(self, config: Config, api: TinkoffAPI):
        """
        Инициализация DataManager.

        Аргументы:
            config: Конфигурация приложения
            api: Обертка Tinkoff API
        """
        self.config = config
        self.api = api
        self.db = DatabaseManager(config)
        self.historical_data: Dict[str, pd.DataFrame] = {}
        self.realtime_data: Dict[str, List[CandleData]] = {}
        self.indicators: Dict[str, Dict[str, IndicatorData]] = {}
        self._running = False

    async def initialize(self):
        """Инициализация менеджера данных."""
        logger.info("Инициализация DataManager")

        # Инициализация подключения к базе данных
        await self.db.connect()

        # Загрузка исторических данных для настроенных инструментов
        await self.load_historical_data(days=30)

        # Подписка на данные в реальном времени
        await self.api.subscribe_to_market_data(list(self.api.instruments.keys()))

        logger.success("DataManager инициализирован")

    async def shutdown(self):
        """Завершение работы менеджера данных."""
        logger.info("Завершение работы DataManager")
        self._running = False
        await self.db.disconnect()
        logger.success("DataManager завершил работу")

    async def load_historical_data(self, days: int = 30):
        """
        Загрузка исторических данных для всех инструментов.

        Аргументы:
            days: Количество дней истории для загрузки
        """
        logger.info(f"Загрузка {days} дней исторических данных")

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        for figi, instrument in self.api.instruments.items():
            candles = await self.api.get_candles(
                figi=figi,
                interval=CandleInterval.CANDLE_INTERVAL_1_HOUR,
                from_dt=start_date,
                to_dt=end_date,
            )

            if candles:
                df = pd.DataFrame([c.dict() for c in candles])
                df.set_index("time", inplace=True)
                self.historical_data[figi] = df

                # Расчет начальных индикаторов
                self._calculate_indicators(figi)

                logger.info(f"Загружено {len(candles)} свечей для {instrument.name}")

        logger.success(f"Исторические данные загружены для {len(self.api.instruments)} инструментов")

    async def run(self):
        """Основной цикл сбора и обработки данных."""
        self._running = True
        logger.info("Запуск основного цикла DataManager")

        try:
            while self._running:
                # Обработка входящих данных в реальном времени
                await self._process_realtime_data()

                # Периодическое обновление индикаторов
                await self._update_indicators()

                # Периодическое сохранение данных в базу данных
                await self._save_data()

                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Ошибка в цикле DataManager: {e}")
            raise

    async def _process_realtime_data(self):
        """Обработка входящих данных в реальном времени и обновление индикаторов."""
        # Вызывается callback'ом потока рыночных данных в TinkoffAPI
        pass

    async def _update_indicators(self):
        """Обновление технических индикаторов для всех инструментов."""
        for figi in self.api.instruments:
            if figi in self.historical_data:
                self._calculate_indicators(figi)

    async def _save_data(self):
        """Сохранение собранных данных в базу данных."""
        # Сохранение свечей
        for figi, candles in self.realtime_data.items():
            if candles:
                await self.db.save_candles(figi, candles)
                self.realtime_data[figi] = []  # Очистка буфера

        # Сохранение индикаторов
        for figi, indicators in self.indicators.items():
            await self.db.save_indicators(figi, indicators)

    def _calculate_indicators(self, figi: str):
        """
        Расчет технических индикаторов для указанного инструмента.

        Аргументы:
            figi: FIGI инструмента
        """
        if figi not in self.historical_data:
            return

        df = self.historical_data[figi]

        # Расчет индикаторов (упрощенные примеры)
        indicators = {}

        # Простые скользящие средние
        indicators["sma_20"] = IndicatorData(
            name="SMA_20",
            values=df["close"].rolling(window=20).mean().values,
            time=df.index,
        )

        indicators["sma_50"] = IndicatorData(
            name="SMA_50",
            values=df["close"].rolling(window=50).mean().values,
            time=df.index,
        )

        # Индекс относительной силы
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        indicators["rsi_14"] = IndicatorData(
            name="RSI_14",
            values=rsi.values,
            time=df.index,
        )

        # Полосы Боллинджера
        sma = df["close"].rolling(window=20).mean()
        std = df["close"].rolling(window=20).std()
        indicators["bollinger_upper"] = IndicatorData(
            name="Bollinger_Upper",
            values=(sma + 2 * std).values,
            time=df.index,
        )
        indicators["bollinger_lower"] = IndicatorData(
            name="Bollinger_Lower",
            values=(sma - 2 * std).values,
            time=df.index,
        )

        self.indicators[figi] = indicators

    async def get_latest_indicators(self, figi: str) -> Dict[str, IndicatorData]:
        """
        Получение последних рассчитанных индикаторов для указанного инструмента.

        Аргументы:
            figi: FIGI инструмента

        Возвращает:
            Словарь имен индикаторов в IndicatorData
        """
        return self.indicators.get(figi, {})

    async def get_historical_indicators(
        self, figi: str, indicator_name: str, lookback: int = 100
    ) -> Optional[List[float]]:
        """
        Получение исторических значений для конкретного индикатора.

        Аргументы:
            figi: FIGI инструмента
            indicator_name: Название индикатора
            lookback: Количество исторических значений для возврата

        Возвращает:
            Список значений индикатора или None, если не найден
        """
        if figi not in self.indicators:
            return None

        indicator = self.indicators[figi].get(indicator_name)
        if not indicator:
            return None

        return indicator.values[-lookback:]

    async def save_trade_result(self, trade):
        """Сохранение результатов сделки в базу данных."""
        await self.db.save_trade(trade)


class DatabaseManager:
    """
    Управляет всеми операциями с базой данных для торгового бота.

    Включает:
    - Хранение исторических и рыночных данных в реальном времени
    - Сохранение результатов сделок
    - Управление снимками портфеля
    - Хранение метрик производительности стратегий
    """

    def __init__(self, config: Config):
        """
        Инициализация DatabaseManager.

        Аргументы:
            config: Конфигурация приложения
        """
        self.config = config
        self._connection = None
        self._data_dir = Path("data")
        self._ensure_data_directory()

    def _ensure_data_directory(self):
        """Обеспечение существования директории данных."""
        self._data_dir.mkdir(exist_ok=True)

    async def connect(self):
        """Подключение к базе данных."""
        # В этой упрощенной версии используются JSON-файлы
        # В реальной реализации здесь было бы подключение к PostgreSQL
        logger.info("DatabaseManager подключен (используются JSON-файлы)")

    async def disconnect(self):
        """Отключение от базы данных."""
        logger.info("DatabaseManager отключен")

    async def save_candles(self, figi: str, candles: List[CandleData]):
        """
        Сохранение данных свечей в базу данных.

        Аргументы:
            figi: FIGI инструмента
            candles: Список данных свечей
        """
        file_path = self._data_dir / f"{figi}_candles.json"

        # Загрузка существующих данных
        existing = []
        if file_path.exists():
            with open(file_path, "r") as f:
                existing = json.load(f)

        # Добавление новых свечей
        existing.extend([c.dict() for c in candles])

        # Сохранение обратно в файл
        with open(file_path, "w") as f:
            json.dump(existing, f)

    async def save_indicators(self, figi: str, indicators: Dict[str, IndicatorData]):
        """
        Сохранение данных индикаторов в базу данных.

        Аргументы:
            figi: FIGI инструмента
            indicators: Словарь данных индикаторов
        """
        file_path = self._data_dir / f"{figi}_indicators.json"

        # Конвертация индикаторов в сериализуемый формат
        data = {
            name: {
                "values": indicator.values.tolist() if hasattr(indicator.values, "tolist") else indicator.values,
                "time": [t.isoformat() for t in indicator.time],
            }
            for name, indicator in indicators.items()
        }

        # Сохранение в файл
        with open(file_path, "w") as f:
            json.dump(data, f)

    async def save_trade(self, trade):
        """
        Сохранение данных сделки в базу данных.

        Аргументы:
            trade: Объект Trade для сохранения
        """
        file_path = self._data_dir / "trades.json"

        # Загрузка существующих сделок
        trades = []
        if file_path.exists():
            with open(file_path, "r") as f:
                trades = json.load(f)

        # Добавление новой сделки
        trades.append(trade.dict())

        # Сохранение обратно в файл
        with open(file_path, "w") as f:
            json.dump(trades, f)

    async def get_trade_history(self, days: int = 30) -> List[dict]:
        """
        Получение истории сделок за указанное количество дней.

        Аргументы:
            days: Количество дней истории для получения

        Возвращает:
            Список словарей сделок
        """
        file_path = self._data_dir / "trades.json"

        if not file_path.exists():
            return []

        with open(file_path, "r") as f:
            trades = json.load(f)

        # Фильтрация по дате (упрощенно)
        return trades[-days:]

    async def get_portfolio_history(self, days: int = 30) -> List[dict]:
        """
        Получение истории портфеля за указанное количество дней.

        Аргументы:
            days: Количество дней истории для получения

        Возвращает:
            Список снимков портфеля
        """
        file_path = self._data_dir / "portfolio.json"

        if not file_path.exists():
            return []

        with open(file_path, "r") as f:
            portfolio = json.load(f)

        # Фильтрация по дате (упрощенно)
        return portfolio[-days:]

# Добавление в файл из скрипта №13
        async def get_historical_candles(
                self,
                figi: str,
                start_date: datetime,
                end_date: datetime,
                interval: str = '1h'
        ) -> pd.DataFrame:
            """
            Получение исторических данных свечей.

            Args:
                figi: Идентификатор инструмента
                start_date: Начальная дата
                end_date: Конечная дата
                interval: Интервал (1m, 5m, 1h, 1d)

            Returns:
                DataFrame с историческими данными
            """
            if figi not in self.historical_data:
                return pd.DataFrame()

            df = self.historical_data[figi]
            mask = (df.index >= start_date) & (df.index <= end_date)
            return df.loc[mask].copy()