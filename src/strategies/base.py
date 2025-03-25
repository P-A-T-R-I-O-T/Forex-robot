# Абстрактный класс торговой стратегии
class TradingStrategy(ABC):
    @abstractmethod
    def analyze(self, data: pd.DataFrame) -> dict:
        """Анализ рыночных данных и генерация торговых сигналов"""
        pass