from datetime import datetime, timedelta
from tinkoff_client import TinkoffClient


class MovingAverageStrategy:
    def __init__(self, tinkoff_client: TinkoffClient):
        self.client = tinkoff_client

    def analyze(self, figi: str):
        candles = self.client.get_candles(
            figi=figi,
            from_dt=datetime.now() - timedelta(days=30),
            to_dt=datetime.now(),
            interval=CandleInterval.CANDLE_INTERVAL_DAY
        )
        # Логика анализа