import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables with defaults."""

    # API Settings
    API_HOST: str = Field("0.0.0.0", description="API host address")
    API_PORT: int = Field(8000, description="API port number")

    # Redis Connection Settings
    REDIS_HOST: str = Field("localhost", description="Redis host")
    REDIS_PORT: int = Field(6379, description="Redis port")
    REDIS_DB: int = Field(0, description="Redis database number")
    REDIS_PASSWORD: Optional[str] = Field(None, description="Redis password")
    REDIS_MAX_CONNECTIONS: int = Field(10, description="Maximum number of Redis connections in pool")
    REDIS_SSL: bool = Field(False, description="Whether to use SSL for Redis connection")

    # Logging Settings
    LOG_LEVEL: str = Field("info", description="Logging level (debug, info, warning, error, critical)")
    LOG_FORMAT: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Redis Cluster Settings
    REDIS_CLUSTER_ENABLED: bool = Field(False, description="Whether to use Redis Cluster")
    REDIS_CLUSTER_NODES: str = Field("localhost:7000,localhost:7001,localhost:7002",
                                     description="Comma-separated list of cluster nodes")

    def get_redis_url(self) -> str:
        if not self.REDIS_CLUSTER_ENABLED:
            auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            protocol = "rediss" if self.REDIS_SSL else "redis"
            return f"{protocol}://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return None

    class Config:
        env_prefix = "APP_"
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_app_settings() -> Settings:
    """
    Create and cache a Settings instance.
    This ensures settings are loaded once during app lifetime.
    """
    return Settings()
