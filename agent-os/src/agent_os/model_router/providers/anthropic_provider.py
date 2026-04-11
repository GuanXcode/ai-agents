"""Anthropic provider adapter."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from agent_os.model_router.providers.base import LLMProvider
from agent_os.model_router.schemas import ModelRequest, ModelResponse


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: str = "claude-sonnet-4-6") -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._default_model = default_model

    def name(self) -> str:
        return "anthropic"

    async def complete(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self._default_model

        messages = [{"role": "user", "content": request.user_message}]

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        response = await self._client.messages.create(**kwargs)

        text_blocks = [b.text for b in response.content if b.type == "text"]
        output = "\n".join(text_blocks)

        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0

        cost_usd = _estimate_cost_anthropic(response.model, input_tokens, output_tokens)

        return ModelResponse(
            output=output,
            model_name=response.model,
            provider=self.name(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost_usd,
        )


def _estimate_cost_anthropic(model: str, input_tokens: int, output_tokens: int) -> float:
    """按 Anthropic 公开定价估算 USD 成本（每百万 token）。"""
    model_lower = model.lower()
    if "haiku" in model_lower:
        input_price, output_price = 0.80, 4.00
    elif "sonnet" in model_lower:
        input_price, output_price = 3.00, 15.00
    else:  # opus or unknown
        input_price, output_price = 15.00, 75.00
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
