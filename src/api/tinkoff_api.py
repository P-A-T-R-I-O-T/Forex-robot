"""
Обертка Tinkoff Invest API v2 для Forex Trading Bot.

Этот модуль предоставляет асинхронный интерфейс к Tinkoff Invest API с:
- Управлением подключением
- Получением рыночных данных
- Исполнением ордеров
- Управлением портфелем
- Обработкой ошибок и повторными попытками
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from loguru import logger
from tinkoff.invest import (
    AsyncClient,
    CandleInterval,
    HistoricCandle,
    MarketDataResponse,
    OrderDirection,
    OrderType,
    PostOrderResponse,
    SecurityTradingStatus,
    Share,
)
from tinkoff.invest.async_services import AsyncServices
from tinkoff.invest.retrying.settings import RetryClientSettings
from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest.schemas import InstrumentIdType

from src.utils.config import Config
from src.models.trade import Trade
from src.data.schemas import CandleData


class TinkoffAPI:
    """
    Обертка для Tinkoff Invest API v2 с асинхронными методами.

    Атрибуты:
        config (Config): Конфигурация приложения
        client (AsyncRetryingClient): Клиент Tinkoff API с механизмом повтора
        instruments (Dict[str, Share]): Кэшированная информация об инструментах
        last_candles (Dict[str, List[HistoricCandle]]): Последние полученные свечи
    """

    def __init__(self, config: Config):
        """
        Инициализация обертки Tinkoff API.

        Аргументы:
            config: Конфигурация приложения с токенами API
        """
        self.config = config
        self.client: Optional[AsyncRetryingClient] = None
        self.instruments: Dict[str, Share] = {}
        self.last_candles: Dict[str, List[HistoricCandle]] = {}
        self._market_data_stream: Optional[AsyncServices.MarketDataStream] = None

    async def connect(self):
        """Подключение к Tinkoff Invest API."""
        logger.info("Подключение к Tinkoff Invest API")

        retry_settings = RetryClientSettings(
            max_retry_attempt=5,
            timeout=timedelta(seconds=30),
            retry_delay=timedelta(seconds=1),
        )

        token = (
            self.config.tinkoff_sandbox_token
            if self.config.environment == "sandbox"
            else self.config.tinkoff_prod_token
        )

        self.client = AsyncRetryingClient(
            token=token,
            settings=retry_settings,
            app_name="ForexTradingBot",
        )

        # Загрузка доступных инструментов
        await self.load_instruments()

        logger.success("Успешное подключение к Tinkoff Invest API")

    async def disconnect(self):
        """Отключение от Tinkoff Invest API."""
        if self.client:
            logger.info("Отключение от Tinkoff Invest API")
            await self.client.__aexit__(None, None, None)
            self.client = None

            if self._market_data_stream:
                await self._market_data_stream.stop()
                self._market_data_stream = None

            logger.success("Отключено от Tinkoff Invest API")

    async def load_instruments(self):
        """Загрузка доступных торговых инструментов (валютных пар)."""
        if not self.client:
            raise RuntimeError("Клиент API не подключен")

        logger.info("Загрузка доступных инструментов")

        response = await self.client.instruments.currencies()
        for currency in response.instruments:
            self.instruments[currency.figi] = currency

        logger.info(f"Загружено {len(self.instruments)} инструментов")

    async def get_current_prices(self, figi_list: List[str]) -> Dict[str, float]:
        """
        Получение текущих цен для указанных инструментов.

        Аргументы:
            figi_list: Список идентификаторов FIGI

        Возвращает:
            Словарь, сопоставляющий FIGI с текущей ценой
        """
        if not self.client:
            raise RuntimeError("Клиент API не подключен")

        prices = {}

        for figi in figi_list:
            last_price = await self.client.market_data.get_last_prices(figi=[figi])
            if last_price.last_prices:
                prices[figi] = self._price_to_float(last_price.last_prices[0].price)

        return prices

    async def get_candles(
        self,
        figi: str,
        interval: CandleInterval,
        from_dt: datetime,
        to_dt: datetime,
    ) -> List[CandleData]:
        """
        Получение исторических свечей для указанного инструмента и временного диапазона.

        Аргументы:
            figi: FIGI инструмента
            interval: Интервал свечи (1min, 5min и т.д.)
            from_dt: Начальная дата и время
            to_dt: Конечная дата и время

        Возвращает:
            Список данных свечей
        """
        if not self.client:
            raise RuntimeError("Клиент API не подключен")

        candles = []

        async for candle in self.client.get_all_candles(
            figi=figi,
            from_=from_dt,
            to=to_dt,
            interval=interval,
        ):
            candles.append(candle)

        # Кэширование последних свечей
        self.last_candles[figi] = candles[-100:]  # Сохраняем последние 100 свечей

        return [
            CandleData(
                open=self._price_to_float(candle.open),
                high=self._price_to_float(candle.high),
                low=self._price_to_float(candle.low),
                close=self._price_to_float(candle.close),
                volume=candle.volume,
                time=candle.time,
            )
            for candle in candles
        ]

    async def place_order(
        self,
        figi: str,
        direction: OrderDirection,
        quantity: int,
        order_type: OrderType = OrderType.ORDER_TYPE_MARKET,
        price: Optional[float] = None,
    ) -> Tuple[bool, Optional[Trade]]:
        """
        Размещение ордера через Tinkoff API.

        Аргументы:
            figi: FIGI инструмента
            direction: BUY или SELL
            quantity: Количество единиц для торговли
            order_type: Рыночный или лимитный ордер
            price: Требуется для лимитных ордеров

        Возвращает:
            Кортеж (успех, Trade), где Trade содержит детали ордера
        """
        if not self.client:
            raise RuntimeError("Клиент API не подключен")

        try:
            response: PostOrderResponse = await self.client.orders.post_order(
                figi=figi,
                quantity=quantity,
                direction=direction,
                account_id=self.config.account_id,
                order_type=order_type,
                price=self._float_to_quotation(price) if price else None,
            )

            if response.execution_report_status in [
                "execution_report_status_fill",
                "execution_report_status_partialfill",
            ]:
                trade = Trade(
                    figi=figi,
                    direction=direction,
                    executed_quantity=quantity,
                    executed_price=self._price_to_float(response.executed_order_price),
                    commission=self._price_to_float(response.total_order_amount),
                    status=response.execution_report_status,
                    order_id=response.order_id,
                    timestamp=datetime.utcnow(),
                )
                return True, trade

            return False, None

        except Exception as e:
            logger.error(f"Не удалось разместить ордер: {e}")
            return False, None

    async def subscribe_to_market_data(self, figi_list: List[str]):
        """
        Подписка на рыночные данные в реальном времени для указанных инструментов.

        Аргументы:
            figi_list: Список идентификаторов FIGI для подписки
        """
        if not self.client:
            raise RuntimeError("Клиент API не подключен")

        self._market_data_stream = self.client.create_market_data_stream()

        # Подписка на свечи и обновления стакана
        await self._market_data_stream.candles.subscribe(
            [(figi, CandleInterval.CANDLE_INTERVAL_1_MIN) for figi in figi_list]
        )

        await self._market_data_stream.order_book.subscribe(figi_list, depth=10)

        # Начало обработки входящих данных
        asyncio.create_task(self._process_market_data())

    async def _process_market_data(self):
        """Обработка входящих рыночных данных из потока."""
        if not self._market_data_stream:
            return

        async for market_data in self._market_data_stream:
            if market_data.candle:
                # Обработка обновления свечи
                figi = market_data.candle.figi
                candle = market_data.candle

                if figi not in self.last_candles:
                    self.last_candles[figi] = []

                self.last_candles[figi].append(candle)
                # Сохраняем только последние 100 свечей
                if len(self.last_candles[figi]) > 100:
                    self.last_candles[figi] = self.last_candles[figi][-100:]

            elif market_data.orderbook:
                # Обработка обновления стакана
                pass

            elif market_data.last_price:
                # Обработка обновления последней цены
                pass

    def _price_to_float(self, price) -> float:
        """Конвертация цены Tinkoff API в float."""
        if hasattr(price, "units") and hasattr(price, "nano"):
            return price.units + price.nano / 1e9
        return float(price)

    def _float_to_quotation(self, value: float):
        """Конвертация float в Quotation Tinkoff API."""
        units = int(value)
        nano = int((value - units) * 1e9)
        return self.client.invest.Quotation(units=units, nano=nano)


async def test_connection(config: Config):
    """Тестирование подключения к Tinkoff API."""
    api = TinkoffAPI(config)
    try:
        await api.connect()

        # Тест получения списка инструментов
        print(f"Загружено {len(api.instruments)} инструментов")

        # Тест получения цен для первых 5 инструментов
        figi_list = list(api.instruments.keys())[:5]
        prices = await api.get_current_prices(figi_list)

        print("Текущие цены:")
        for figi, price in prices.items():
            print(f"{api.instruments[figi].name}: {price}")

        return True
    except Exception as e:
        print(f"Тест подключения не удался: {e}")
        return False
    finally:
        await api.disconnect()
