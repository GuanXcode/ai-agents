"""Agent OS configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    url: str = "postgresql+asyncpg://root:123456@127.0.0.1:5432/agentos"
    pool_size: int = 10
    max_overflow: int = 20


class GatewaySettings(BaseSettings):
    rate_limit_per_tenant: int = 100


class OrchestratorSettings(BaseSettings):
    default_timeout_sec: int = 120
    default_budget_usd: float = 10.0
    default_max_retries: int = 3
    retry_base_delay_sec: float = 1.0
    human_approval_timeout_sec: int = 1800


class ProviderSettings(BaseSettings):
    api_key_env: str = ""
    default_model: str = ""


class RoutingRule(BaseSettings):
    primary: str
    primary_model: str
    fallback: str
    fallback_model: str


class CircuitBreakerSettings(BaseSettings):
    failure_threshold: int = 3
    reset_timeout_sec: int = 30


class ModelRouterSettings(BaseSettings):
    providers: dict[str, ProviderSettings] = {}
    routing: dict[str, RoutingRule] = {}
    circuit_breaker: CircuitBreakerSettings = CircuitBreakerSettings()


class ShortTermMemorySettings(BaseSettings):
    max_rounds: int = 10


class LongTermMemorySettings(BaseSettings):
    summary_max_chars: int = 200


class MemorySettings(BaseSettings):
    short_term: ShortTermMemorySettings = ShortTermMemorySettings()
    long_term: LongTermMemorySettings = LongTermMemorySettings()


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    json_format: bool = True


class TracingSettings(BaseSettings):
    enabled: bool = True
    exporter: str = "otlp"
    endpoint: str = "http://localhost:4317"


class MetricsSettings(BaseSettings):
    enabled: bool = True


class ObservabilitySettings(BaseSettings):
    logging: LoggingSettings = LoggingSettings()
    tracing: TracingSettings = TracingSettings()
    metrics: MetricsSettings = MetricsSettings()


class Settings(BaseSettings):
    app_name: str = "agent-os"
    debug: bool = False
    database: DatabaseSettings = DatabaseSettings()
    gateway: GatewaySettings = GatewaySettings()
    orchestrator: OrchestratorSettings = OrchestratorSettings()
    model_router: ModelRouterSettings = ModelRouterSettings()
    memory: MemorySettings = MemorySettings()
    observability: ObservabilitySettings = ObservabilitySettings()

    @classmethod
    def from_yaml(cls, path: str | Path) -> Settings:
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return cls(**data)


def load_settings() -> Settings:
    config_path = os.getenv("AGENT_OS_CONFIG", "configs/default.yaml")
    settings = Settings.from_yaml(config_path) if Path(config_path).exists() else Settings()

    # 允许用环境变量覆盖数据库 URL（容器部署时使用）
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        settings.database.url = db_url

    return settings
