#  Работа с потоковыми данными


from tinkoff.invest import (
    AsyncClient,
    MarketDataStreamManager,
    SubscribeCandlesRequest,
    CandleInstrument,
    CandleInterval
)
from src.data.converters import candles_to_ohlc


class DataStreamer:
    def __init__(self, token: str):
        self.token = token
        self.stream_manager = None

    async def subscribe_to_candles(self, figi: str, interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_1_MIN):
        """Подписка на поток свечей"""
        async with AsyncClient(self.token) as client:
            self.stream_manager = client.create_market_data_stream()

            request = SubscribeCandlesRequest(
                instruments=[CandleInstrument(figi=figi, interval=interval)],
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE
            )

            await self.stream_manager.subscribe_candles(request)

            async for candle in self.stream_manager:
                yield candles_to_ohlc([candle])