"""OpenAI provider adapter."""

from __future__ import annotations

from openai import AsyncOpenAI

from agent_os.model_router.providers.base import LLMProvider
from agent_os.model_router.schemas import ModelRequest, ModelResponse


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: str = "gpt-4o") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._default_model = default_model

    def name(self) -> str:
        return "openai"

    async def complete(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self._default_model

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_message})

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost_usd = _estimate_cost_openai(response.model, input_tokens, output_tokens)

        return ModelResponse(
            output=choice.message.content or "",
            model_name=response.model,
            provider=self.name(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=usage.total_tokens if usage else 0,
            cost_usd=cost_usd,
        )


def _estimate_cost_openai(model: str, input_tokens: int, output_tokens: int) -> float:
    """按 OpenAI 公开定价估算 USD 成本（每百万 token）。"""
    model_lower = model.lower()
    if "mini" in model_lower:
        input_price, output_price = 0.15, 0.60
    elif "gpt-4o" in model_lower:
        input_price, output_price = 2.50, 10.00
    else:  # gpt-4 or unknown
        input_price, output_price = 10.00, 30.00
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
