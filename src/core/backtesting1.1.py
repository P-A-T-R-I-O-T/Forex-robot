"""
Модуль бэктестинга торговых стратегий.
Включает:
- Тестирование на исторических данных
- Оптимизацию параметров
- Оценку результатов через метрики
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from loguru import logger
import optuna
from optuna.samplers import TPESampler
from sklearn.model_selection import ParameterGrid

from src.strategies.base_strategy import BaseStrategy
from src.data.data_manager import DataManager
from src.models.portfolio import Portfolio
from src.utils.config import Config


class Backtester:
    """
    Класс для бэктестинга и оптимизации торговых стратегий.

    Атрибуты:
        strategy (BaseStrategy): Стратегия для тестирования
        data_manager (DataManager): Менеджер данных
        config (Config): Конфигурация
        results (pd.DataFrame): Результаты тестов
    """

    def __init__(self, strategy: BaseStrategy, data_manager: DataManager, config: Config):
        self.strategy = strategy
        self.data_manager = data_manager
        self.config = config
        self.results = pd.DataFrame()
        self._best_params = {}

    async def run_backtest(
            self,
            start_date: datetime,
            end_date: datetime,
            initial_balance: float = 10000,
    ) -> Dict[str, float]:
        """
        Запуск бэктеста стратегии на исторических данных.

        Аргументы:
            start_date: Начальная дата
            end_date: Конечная дата
            initial_balance: Начальный баланс

        Возвращает:
            Словарь с метриками производительности
        """
        logger.info(f"Запуск бэктеста с {start_date} по {end_date}")

        # Инициализация портфеля
        portfolio = Portfolio(self.config, None)
        await portfolio.initialize()
        portfolio.update_balance('USD', initial_balance)

        # Получение исторических данных
        historical_data = {}
        for figi in self.strategy.instruments:
            candles = await self.data_manager.get_historical_candles(
                figi=figi,
                start_date=start_date,
                end_date=end_date,
                interval='1h'
            )
            if candles:
                historical_data[figi] = candles

        if not historical_data:
            raise ValueError("Нет исторических данных для бэктестинга")

        # Симуляция торговли
        trades = []
        equity_curve = []
        current_date = start_date

        while current_date <= end_date:
            for figi, data in historical_data.items():
                # Получаем данные для текущей даты
                current_data = data[data['time'] <= current_date].tail(100)
                if len(current_data) < 20:
                    continue

                # Генерируем сигналы
                signals = await self.strategy.generate_signals(figi, current_data)

                # Исполнение сигналов
                for signal in signals:
                    trade = await self._execute_signal(
                        signal=signal,
                        portfolio=portfolio,
                        current_price=current_data.iloc[-1]['close']
                    )
                    if trade:
                        trades.append(trade)

            # Запись состояния портфеля
            equity_curve.append({
                'date': current_date,
                'balance': portfolio.get_balance('USD'),
                'equity': portfolio.total_equity()
            })

            current_date += timedelta(days=1)

        # Расчет метрик
        metrics = self._calculate_metrics(trades, equity_curve)

        logger.success(f"Бэктест завершен. Коэффициент Шарпа: {metrics['sharpe_ratio']:.2f}")
        return metrics

    # ... (остальные методы с переведенными комментариями)

    def _calculate_metrics(
            self,
            trades: List[Dict],
            equity_curve: List[Dict]
    ) -> Dict[str, float]:
        """
        Расчет метрик производительности.

        Аргументы:
            trades: Список сделок
            equity_curve: Кривая баланса

        Возвращает:
            Словарь с метриками
        """
        if not trades or not equity_curve:
            return {
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_return': 0,
                'sortino_ratio': 0
            }

        # Конвертируем в DataFrame
        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity_curve)
        equity_df.set_index('date', inplace=True)

        # Рассчитываем доходности
        equity_df['returns'] = equity_df['equity'].pct_change()
        equity_df['cum_returns'] = (1 + equity_df['returns']).cumprod()

        # Sharpe Ratio
        sharpe_ratio = np.sqrt(252) * equity_df['returns'].mean() / equity_df['returns'].std()

        # Sortino Ratio
        downside_returns = equity_df[equity_df['returns'] < 0]['returns']
        sortino_ratio = np.sqrt(252) * equity_df[
            'returns'].mean() / downside_returns.std() if not downside_returns.empty else 0

        # Max Drawdown
        roll_max = equity_df['cum_returns'].cummax()
        drawdown = equity_df['cum_returns'] / roll_max - 1
        max_drawdown = drawdown.min()

        # Win Rate
        win_rate = (trades_df['profit'] > 0).mean() if 'profit' in trades_df.columns else 0

        # Profit Factor
        gross_profit = trades_df[trades_df['profit'] > 0]['profit'].sum() if 'profit' in trades_df.columns else 0
        gross_loss = abs(trades_df[trades_df['profit'] < 0]['profit'].sum()) if 'profit' in trades_df.columns else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

        # Total Return
        initial_equity = equity_df.iloc[0]['equity']
        final_equity = equity_df.iloc[-1]['equity']
        total_return = (final_equity - initial_equity) / initial_equity

        return {
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'sortino_ratio': sortino_ratio,
            'num_trades': len(trades_df),
            'avg_trade': trades_df['profit'].mean() if 'profit' in trades_df.columns else 0
        }