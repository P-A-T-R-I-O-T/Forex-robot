"""
Изучение библиотек MetaTrader API, OANDA API и др

pip install metaapi-cloud-sdk



MQL4-Python
pyMT4
MQL4-Python-Bridge
"""
from metaapi_cloud_sdk import MetaStats

token = '...'
api = MetaStats(token=token)



account_id = '...'  #  MetaApi account id


# получение статистики по счету MetaTrader с помощью Meta Api
print(await MetaStats.get_metrics(account_id=account_id))

# получение статистики по счетам MetaTrader с использованием Meta Api, включая открытые позиции
print(await MetaStats.get_metrics(account_id=account_id, include_open_positions=True))

# получение данных о сделках на счете MetaTrader с использованием Meta Api
print(await MetaStats.get_account_trades(account_id=account_id, start_time='2020-01-01 00:00:00.000', end_time='2021-01-01 00:00:00.000'))

# извлекать данные из Meta Api для открытия сделок на счете MetaTrader
print(await MetaStats.get_account_open_trades(account_id=account_id))
