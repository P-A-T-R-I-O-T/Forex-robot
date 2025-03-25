# Конкретная реализация стратегии (скользящие средние)
class MovingAverageStrategy(TradingStrategy):
    def analyze(self, data: pd.DataFrame) -> dict:
        """Стратегия на основе пересечения SMA20 и SMA50"""
        # Расчет индикаторов
        data['sma20'] = data['close'].rolling(20).mean()
        data['sma50'] = data['close'].rolling(50).mean()

        last_row = data.iloc[-1]  # Последняя доступная свеча

        # Генерация сигнала
        if last_row['sma20'] > last_row['sma50']:
            return {'action': 'buy', 'strength': 0.8}
        else:
            return {'action': 'sell', 'strength': 0.6}