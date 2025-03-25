# Импорт необходимых библиотек
import os  # Для работы с переменными окружения
import datetime  # Для работы с датами/временем
import pandas as pd  # Для анализа данных
from tinkoff.invest import (
    Client,
    MarketDataStreamService,
    SubscribeCandlesRequest,
    CandleInstrument,
    CandleInterval,
    SubscriptionAction,
    OrderDirection,
    OrderType,)  # Импорт компонентов API Тинькофф
from abc import ABC, abstractmethod  # Для создания абстрактных классов

# Блок конфигурации
TOKEN = os.getenv("TINKOFF_TOKEN")  # Токен авторизации из переменных окружения
ACCOUNT_ID = "ваш_номер_счета"  # Идентификатор торгового счета
REPORTS_DIR = "отчеты"  # Директория для хранения отчетов














# Точка входа в программу
if __name__ == "__main__":
    ai = TradingAI()  # Инициализация ИИ
    ai.run()  # Запуск торговой системы