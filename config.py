import os
from typing import Optional
from pydantic import BaseSettings, validator, Field


class Settings(BaseSettings):
    # Конфигурация среды
    ENVIRONMENT: str = Field(..., env="ENVIRONMENT")

    # Токены Tinkoff API
    TINKOFF_SANDBOX_TOKEN: str = Field(..., env="TINKOFF_SANDBOX_TOKEN")
    TINKOFF_PROD_TOKEN: str = Field(..., env="TINKOFF_PROD_TOKEN")
    TINKOFF_ACCOUNT_ID: Optional[str] = Field(None, env="TINKOFF_ACCOUNT_ID")

    # Конфигурация базы данных
    DB_HOST: str = Field(..., env="DB_HOST")
    DB_PORT: int = Field(..., env="DB_PORT")
    DB_NAME: str = Field(..., env="DB_NAME")
    DB_USER: str = Field(..., env="DB_USER")
    DB_PASSWORD: str = Field(..., env="DB_PASSWORD")

    # Конфигурация Redis
    REDIS_HOST: str = Field(..., env="REDIS_HOST")
    REDIS_PORT: int = Field(..., env="REDIS_PORT")

    # Параметры торговли
    INITIAL_BALANCE: float = Field(..., env="INITIAL_BALANCE")
    RISK_PER_TRADE: float = Field(..., env="RISK_PER_TRADE")
    MAX_OPEN_TRADES: int = Field(..., env="MAX_OPEN_TRADES")

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in ("development", "sandbox", "production"):
            raise ValueError("ENVIRONMENT must be either 'development', 'sandbox' or 'production'")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def tinkoff_token(self) -> str:
        return self.TINKOFF_PROD_TOKEN if self.is_production else self.TINKOFF_SANDBOX_TOKEN

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Глобальный экземпляр конфигурации
config = Settings()

# Необязательно: для лучшей поддержки IDE и подсказок по типам
__all__ = ["config"]