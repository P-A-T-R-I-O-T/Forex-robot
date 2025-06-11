import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Union

from tinkoff.invest import (
    Client,
    CandleInterval,
    HistoricCandle,
    InstrumentIdType,
    MarketDataResponse,
    SubscribeCandlesRequest,
    SubscriptionAction,
    SubscriptionInterval,
    InstrumentStatus,
)
from tinkoff.invest.services import InstrumentsService, MarketDataService, Services
from tinkoff.invest.utils import quotation_to_decimal

logger = logging.getLogger(__name__)


class TinkoffClient:
    def __init__(self, token: str, app_name: str = "ForexRobot"):
        """
        Инициализация клиента Tinkoff Invest API.

        :param token: Токен доступа Tinkoff Invest API
        :param app_name: Название приложения (отображается в статистике использования API)
        """
        self.token = token
        self.app_name = app_name
        self.client = None

    def __enter__(self):
        self.client = Client(self.token, app_name=self.app_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.__exit__(exc_type, exc_val, exc_tb)

    def get_instruments_service(self) -> InstrumentsService:
        """Получить сервис для работы с инструментами"""
        return self.client.instruments

    def get_market_data_service(self) -> MarketDataService:
        """Получить сервис для работы с рыночными данными"""
        return self.client.market_data

    def get_all_services(self) -> Services:
        """Получить все доступные сервисы"""
        return self.client

    def get_candles(
            self,
            figi: str,
            from_dt: datetime,
            to_dt: datetime,
            interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_1_MIN,
    ) -> List[HistoricCandle]:
        """
        Получить исторические свечи для инструмента.

        :param figi: FIGI инструмента
        :param from_dt: Начальная дата периода
        :param to_dt: Конечная дата периода
        :param interval: Интервал свечей (по умолчанию 1 минута)
        :return: Список исторических свечей
        """
        with self.client as client:
            return list(
                client.get_all_candles(
                    figi=figi,
                    from_=from_dt,
                    to=to_dt,
                    interval=interval,
                )
            )

    def get_last_price(self, figi: str) -> float:
        """
        Получить последнюю цену инструмента.

        :param figi: FIGI инструмента
        :return: Последняя цена инструмента
        """
        with self.client as client:
            last_price = client.market_data.get_last_prices(figi=[figi]).last_prices[0]
            return float(quotation_to_decimal(last_price.price))

    def find_instrument_by_ticker(self, ticker: str) -> Optional[Dict]:
        """
        Найти инструмент по тикеру.

        :param ticker: Тикер инструмента
        :return: Информация об инструменте или None, если не найден
        """
        with self.client as client:
            instruments = client.instruments
            for method in [
                instruments.shares,
                instruments.bonds,
                instruments.etfs,
                instruments.currencies,
                instruments.futures,
            ]:
                try:
                    found = list(method(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments)
                    for instrument in found:
                        if instrument.ticker == ticker:
                            return {
                                "figi": instrument.figi,
                                "ticker": instrument.ticker,
                                "name": instrument.name,
                                "currency": instrument.currency,
                                "type": instrument.__class__.__name__,
                            }
                except Exception as e:
                    logger.warning(f"Error searching in {method.__name__}: {e}")
            return None

    def subscribe_to_candles(
            self,
            figi: str,
            interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_1_MIN,
            callback: Optional[callable] = None,
    ):
        """
        Подписаться на поток свечей.

        :param figi: FIGI инструмента
        :param interval: Интервал свечей
        :param callback: Функция обратного вызова для обработки новых свечей
        """
        request = SubscribeCandlesRequest(
            subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
            instruments=[
                {
                    "figi": figi,
                    "interval": interval,
                }
            ],
            waiting_close=True,
        )

        with self.client as client:
            for market_data in client.create_market_data_stream([request]):
                if isinstance(market_data, MarketDataResponse) and market_data.candle:
                    if callback:
                        callback(market_data.candle)

    @staticmethod
    def candle_to_dict(candle: Union[HistoricCandle, MarketDataResponse]) -> Dict:
        """
        Преобразовать свечу в словарь.

        :param candle: Свеча
        :return: Словарь с данными свечи
        """
        if isinstance(candle, MarketDataResponse):
            candle = candle.candle

        return {
            "open": float(quotation_to_decimal(candle.open)),
            "high": float(quotation_to_decimal(candle.high)),
            "low": float(quotation_to_decimal(candle.low)),
            "close": float(quotation_to_decimal(candle.close)),
            "volume": candle.volume,
            "time": candle.time,
            "is_complete": candle.is_complete,
        }