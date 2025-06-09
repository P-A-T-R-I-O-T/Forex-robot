"""
Тесты для модуля бэктестинга.
"""

import pytest
from datetime import datetime, timedelta
from src.core.backtesting import Backtester
from src.strategies.mean_reversion import MeanReversionStrategy
from src.data.data_manager import DataManager
from src.utils.config import Config


@pytest.fixture
def backtester():
    config = Config()
    data_manager = DataManager(config, None)
    strategy = MeanReversionStrategy(config, data_manager)
    return Backtester(strategy, data_manager, config)


@pytest.mark.asyncio
async def test_backtest(backtester):
    start_date = datetime.utcnow() - timedelta(days=30)
    end_date = datetime.utcnow()

    metrics = await backtester.run_backtest(start_date, end_date)

    assert isinstance(metrics, dict)
    assert 'sharpe_ratio' in metrics
    assert 'max_drawdown' in metrics
    assert 'win_rate' in metrics


@pytest.mark.asyncio
async def test_optimization(backtester):
    start_date = datetime.utcnow() - timedelta(days=30)
    end_date = datetime.utcnow()

    best_params = await backtester.optimize_parameters(
        start_date,
        end_date,
        optimization_method='grid',
        n_trials=5
    )

    assert isinstance(best_params, dict)
    assert len(best_params) > 0