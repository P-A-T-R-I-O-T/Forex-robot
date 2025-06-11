from typing import Optional, List
from pydantic import BaseSettings, validator, Field, PostgresDsn, RedisDsn


class Settings(BaseSettings):
    # Конфигурация среды
    ENVIRONMENT: str = Field(..., env="ENVIRONMENT")
    DEBUG: bool = Field(False, env="DEBUG")

    # API конфигурация
    FOREX_API_KEY: str = Field(..., env="FOREX_API_KEY")
    FOREX_API_SECRET: str = Field(..., env="FOREX_API_SECRET")
    FOREX_API_URL: str = Field("https://api.forex-broker.com/v1", env="FOREX_API_URL")

    # Параметры торговой стратегии
    RISK_PER_TRADE: float = Field(0.01, env="RISK_PER_TRADE")
    TAKE_PROFIT_RATIO: float = Field(1.5, env="TAKE_PROFIT_RATIO")
    STOP_LOSS_PIPS: int = Field(50, env="STOP_LOSS_PIPS")
    MAX_OPEN_TRADES: int = Field(5, env="MAX_OPEN_TRADES")
    TRADE_SIZE: float = Field(0.1, env="TRADE_SIZE")
    ALLOWED_PAIRS: List[str] = Field(["EURUSD", "GBPUSD", "USDJPY"], env="ALLOWED_PAIRS")

    # Технические индикаторы
    RSI_PERIOD: int = Field(14, env="RSI_PERIOD")
    MA_PERIOD: int = Field(50, env="MA_PERIOD")
    BOLLINGER_PERIOD: int = Field(20, env="BOLLINGER_PERIOD")

    # База данных
    DB_HOST: str = Field("localhost", env="DB_HOST")
    DB_PORT: int = Field(5432, env="DB_PORT")
    DB_NAME: str = Field("forex_robot", env="DB_NAME")
    DB_USER: str = Field("robot_user", env="DB_USER")
    DB_PASSWORD: str = Field("secure_password", env="DB_PASSWORD")

    # Redis
    REDIS_HOST: str = Field("localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")

    # Логирование
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FILE: str = Field("forex_robot.log", env="LOG_FILE")

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in ("development", "testing", "production"):
            raise ValueError("Invalid environment")
        return v.lower()

    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        v = v.upper()
        if v not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("Invalid log level")
        return v

    @property
    def database_url(self) -> PostgresDsn:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url(self) -> RedisDsn:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"


# Инициализация конфига
config = Settings()

# Для поддержки IDE
__all__ = ["config"]