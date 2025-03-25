#  Конвертация данных API в pandas DataFrame


import pandas as pd
from tinkoff.invest import Candle

def candle_to_df(candle: Candle) -> pd.DataFrame:
    """Конвертирует свечу Tinkoff API в pandas DataFrame"""
    return pd.DataFrame({
        'open': [candle.open.units + candle.open.nano / 1e9],
        'high': [candle.high.units + candle.high.nano / 1e9],
        'low': [candle.low.units + candle.low.nano / 1e9],
        'close': [candle.close.units + candle.close.nano / 1e9],
        'volume': [candle.volume],
        'time': [candle.time]
    }, index=[0])

def candles_to_ohlc(candles: list[Candle]) -> pd.DataFrame:
    """Конвертирует список свечей в OHLC DataFrame"""
    df = pd.concat([candle_to_df(c) for c in candles])
    df.set_index('time', inplace=True)
    return df