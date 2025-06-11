from tinkoff_client import TinkoffClient
from config import TINKOFF_TOKEN  # Предполагается, что токен хранится в config.py

def main():
    with TinkoffClient(token=TINKOFF_TOKEN) as client:
        # Здесь можно вызвать методы для тестирования или передать client дальше
        candles = client.get_candles(
            figi="BBG0013HGFT4",
            from_dt=datetime.now() - timedelta(days=7),
            to_dt=datetime.now(),
            interval=CandleInterval.CANDLE_INTERVAL_HOUR
        )
        print(f"Received {len(candles)} candles")

if __name__ == "__main__":
    main()