from src.strategies.base import TradingStrategy
from src.strategies.moving_avg import MovingAverageStrategy
from src.core.strategy import StrategySelector
from src.core.risk import RiskManager
from src.execution.executors import TradeExecutor
from src.reporting.reports import ReportGenerator
from src.data.streams import AsyncDataStream
from src.utils.config import Config
from src.utils.logger import setup_logger

from tinkoff.invest import AsyncClient
from src.data.streams import DataStreamer
from src.data.converters import candles_to_ohlc
from src.utils.config import Config
from src.utils.logger import setup_logger


class TradingAI:
    def __init__(self):
        self.config = Config()
        self.logger = setup_logger()
        self.streamer = DataStreamer(self.config.TOKEN)

    async def run(self):
        """Основной цикл обработки данных"""
        async for df in self.streamer.subscribe_to_candles(
                figi="BBG004730N88",  # FIGI Сбербанка
                interval=CandleInterval.CANDLE_INTERVAL_1_MIN
        ):
            self.logger.info(f"Получены данные:\n{df.tail()}")
            # Здесь будет основная логика обработки



# Основной класс торгового ИИ
class TradingAI:
    def __init__(self):
        self.client = Client(TOKEN)  # Инициализация клиента API
        self.strategy_selector = StrategySelector()  # Селектор стратегий
        self.risk_manager = RiskManager()  # Менеджер рисков
        self.executor = TradeExecutor(self.client)  # Исполнитель ордеров
        self.reporter = ReportGenerator()  # Генератор отчетов
        self.trades = []  # История сделок

    def stream_data(self):
        """Подписка на поток рыночных данных"""
        stream: MarketDataStreamService = self.client.create_market_data_stream()
        stream.candles.waiting_close().subscribe(self.process_candles)  # Обработка закрытия свечи

        # Настройка подписки для конкретного инструмента
        subscription = SubscribeCandlesRequest(
            subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
            instruments=[
                CandleInstrument(
                    figi="BBG004730N88",  # Пример FIGI (акция Сбербанка)
                    interval=CandleInterval.CANDLE_INTERVAL_1_MIN  # Таймфрейм 1 минута
                )
            ]
        )
        stream.send(subscription)  # Активация подписки

    def process_candles(self, candle):
        """Обработка новой свечи"""
        data = self.convert_candle_to_df(candle)  # Конвертация в DataFrame
        selected_strategy = self.strategy_selector.select_best_strategy(data)  # Выбор стратегии
        decision = self.strategies[selected_strategy].analyze(data)  # Анализ данных

        if self.risk_manager.check_risk(decision):  # Проверка рисков
            order = self.create_order(decision)  # Формирование ордера
            self.executor.execute_order(order)  # Исполнение ордера
            self.trades.append(order)  # Запись в историю

    def convert_candle_to_df(self, candle) -> pd.DataFrame:
        """Конвертация объекта свечи в DataFrame (требует реализации)"""
        pass

    def daily_report_task(self):
        """Ежедневная генерация отчета"""
        self.reporter.generate_daily_report(self.trades)
        self.trades = []  # Очистка истории сделок

    def run(self):
        """Основной метод запуска системы"""
        self.stream_data()  # Запуск потока данных