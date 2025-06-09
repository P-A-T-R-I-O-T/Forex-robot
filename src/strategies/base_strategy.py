def get_parameter_grid(self) -> Dict[str, List]:
    """
    Возвращает сетку параметров для оптимизации.

    Returns:
        Словарь с параметрами и их возможными значениями
    """
    return {
        'window': [10, 20, 30, 50],
        'threshold': [0.5, 1.0, 1.5, 2.0],
    }


def suggest_parameters(self, trial: optuna.Trial) -> Dict:
    """
    Предлагает параметры для оптимизации через Optuna.

    Args:
        trial: Объект испытания Optuna

    Returns:
        Словарь с параметрами
    """
    return {
        'window': trial.suggest_int('window', 10, 50),
        'threshold': trial.suggest_float('threshold', 0.1, 3.0),
    }


def set_parameters(self, **params):
    """
    Устанавливает параметры стратегии.

    Args:
        params: Параметры для установки
    """
    for key, value in params.items():
        if hasattr(self, key):
            setattr(self, key, value)