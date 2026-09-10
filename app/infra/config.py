from functools import lru_cache

from mireacrm_common.config import ServiceSettings
from pydantic_settings import SettingsConfigDict


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(env_prefix="CORE_", env_file=".env", extra="ignore")

    service_name: str = "core-service"
    postgres_dsn: str = "postgresql+asyncpg://core_user:core_pass@localhost:5432/core_db"
    http_port: int = 8001
    grpc_port: int = 9001



@lru_cache
def get_settings() -> Settings:
    return Settings()
