"""Model Router implementation — route steps to LLM providers with fallback and circuit breaker."""

from __future__ import annotations

import os
import time

import structlog

from agent_os.config import ModelRouterSettings
from agent_os.model_router.circuit_breaker import CircuitBreaker
from agent_os.model_router.interface import ModelRouterInterface
from agent_os.model_router.providers.anthropic_provider import AnthropicProvider
from agent_os.model_router.providers.base import LLMProvider
from agent_os.model_router.providers.openai_provider import OpenAIProvider
from agent_os.model_router.schemas import ModelRequest, ModelResponse
from agent_os.orchestrator.schemas import StepInput

logger = structlog.get_logger(__name__)


class ModelUnavailableError(Exception):
    """所有模型均不可用。"""


class ModelRouter(ModelRouterInterface):
    def __init__(self, settings: ModelRouterSettings) -> None:
        self._settings = settings
        self._providers: dict[str, LLMProvider] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        """根据配置初始化 LLM Provider 实例。"""
        for name, provider_cfg in self._settings.providers.items():
            api_key = os.getenv(provider_cfg.api_key_env, "")
            if not api_key:
                logger.warning("provider_api_key_missing", provider=name, env_var=provider_cfg.api_key_env)
                continue

            if name == "openai":
                self._providers[name] = OpenAIProvider(api_key, provider_cfg.default_model)
            elif name == "anthropic":
                self._providers[name] = AnthropicProvider(api_key, provider_cfg.default_model)
            else:
                logger.warning("unknown_provider", provider=name)

            cb_cfg = self._settings.circuit_breaker
            self._breakers[name] = CircuitBreaker(
                failure_threshold=cb_cfg.failure_threshold,
                reset_timeout_sec=cb_cfg.reset_timeout_sec,
            )

    async def route(self, step: StepInput, context: dict | None = None) -> ModelResponse:
        """按步骤 action_type 路由到合适模型，含 fallback 和熔断。"""
        action_type = step.action_type.value if step.action_type else "reason"
        rule = self._settings.routing.get(action_type)
        if rule is None:
            rule = self._settings.routing.get("reason")

        if rule is None:
            raise ModelUnavailableError("无可用路由规则")

        # 构造请求
        request = ModelRequest(
            action_type=action_type,
            system_prompt=step.context.get("system_prompt", "") if step.context else "",
            user_message=step.instruction,
        )

        # 尝试首选 Provider
        response = await self._try_call(rule.primary, rule.primary_model, request)
        if response is not None:
            return response

        logger.warning("primary_model_failed, trying fallback", action_type=action_type)

        # 尝试 Fallback Provider
        response = await self._try_call(rule.fallback, rule.fallback_model, request)
        if response is not None:
            return response

        raise ModelUnavailableError(f"首选和 fallback 模型均不可用 (action_type={action_type})")

    async def _try_call(
        self, provider_name: str, model_name: str, request: ModelRequest
    ) -> ModelResponse | None:
        """尝试调用指定 provider，失败返回 None。"""
        provider = self._providers.get(provider_name)
        breaker = self._breakers.get(provider_name)

        if provider is None:
            logger.warning("provider_not_initialized", provider=provider_name)
            return None

        if breaker and not breaker.allow_request():
            logger.warning("circuit_breaker_open", provider=provider_name)
            return None

        start = time.monotonic()
        try:
            request.model = model_name
            response = await provider.complete(request)
            if breaker:
                breaker.record_success()
            response.latency_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "model_call_succeeded",
                provider=provider_name,
                model=model_name,
                latency_ms=response.latency_ms,
                tokens=response.total_tokens,
            )
            return response
        except Exception as e:
            if breaker:
                breaker.record_failure()
            logger.error(
                "model_call_failed",
                provider=provider_name,
                model=model_name,
                error=str(e),
            )
            return None
