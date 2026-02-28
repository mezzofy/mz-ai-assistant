"""
KimiClient — Async Kimi (Moonshot) API client for the Mezzofy AI Assistant.

Kimi uses an OpenAI-compatible API, so this uses openai.AsyncOpenAI
with a custom base_url pointing to api.moonshot.cn.

Routing: Chinese-language content and APAC market research → Kimi
Config section: config["llm"]["kimi"]
"""

import logging
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger("mezzofy.llm.kimi")


class KimiClient:
    """
    Async wrapper around the Kimi / Moonshot API (OpenAI-compatible).

    Tool definitions follow OpenAI function-calling format
    (which matches ToolExecutor's output format directly).
    """

    def __init__(self, config: dict):
        """
        Args:
            config: Full config dict. Reads from config["llm"]["kimi"].
        """
        from openai import AsyncOpenAI

        kimi_cfg = config.get("llm", {}).get("kimi", {})
        self._api_key: str = kimi_cfg.get("api_key", "")
        self._model: str = kimi_cfg.get("model", "moonshot-v1-128k")
        self._base_url: str = kimi_cfg.get("base_url", "https://api.moonshot.cn/v1")
        self._max_tokens: int = int(kimi_cfg.get("max_tokens", 4096))
        self._temperature: float = float(kimi_cfg.get("temperature", 0.7))

        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )
        logger.info(f"KimiClient ready (model={self._model}, base_url={self._base_url})")

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """
        Send a chat request to Kimi.

        Args:
            messages: Conversation history in OpenAI format.
                      [{"role": "user"|"assistant"|"system", "content": str}, ...]
            tools: Optional list of tool definitions in OpenAI function-calling format.
            system: System prompt. Prepended as a {"role": "system"} message.
            max_tokens: Override max_tokens for this request.

        Returns:
            {
                "content": str,             # Text response (if no tool calls)
                "tool_calls": [...] | None, # Tool calls requested by model
                "stop_reason": str,         # "stop" | "tool_calls" | "length"
                "usage": {"input_tokens": int, "output_tokens": int},
                "model": str,
            }
        """
        full_messages = list(messages)
        if system:
            # Prepend system message (OpenAI style)
            full_messages = [{"role": "system", "content": system}] + full_messages

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": self._temperature,
            "messages": full_messages,
        }

        if tools:
            # Kimi uses OpenAI tool format — pass ToolExecutor definitions directly
            kwargs["tools"] = self._format_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"KimiClient.chat failed: {e}")
            raise

    async def stream_chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a chat response token by token (for WebSocket delivery).

        Yields text chunks as they arrive from the API.
        """
        full_messages = list(messages)
        if system:
            full_messages = [{"role": "system", "content": system}] + full_messages

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=full_messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"KimiClient.stream_chat failed: {e}")
            raise

    # ── Private helpers ───────────────────────────────────────────────────────

    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """
        Convert ToolExecutor definition format to OpenAI function-calling format.

        ToolExecutor format:
            {"name": "...", "description": "...", "parameters": {...JSON Schema...}}

        OpenAI/Kimi format:
            {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    def _parse_response(self, response) -> dict:
        """
        Normalize OpenAI-format Kimi API response to internal format.
        """
        choice = response.choices[0] if response.choices else None
        if not choice:
            return {
                "content": "",
                "tool_calls": None,
                "stop_reason": "empty",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "model": self._model,
            }

        message = choice.message
        content_text = message.content or ""
        tool_calls = None

        if message.tool_calls:
            import json
            tool_calls = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        usage = response.usage
        return {
            "content": content_text,
            "tool_calls": tool_calls,
            "stop_reason": choice.finish_reason or "stop",
            "usage": {
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
            },
            "model": response.model or self._model,
        }

    def _build_tool_result_message(
        self,
        tool_call_id: str,
        tool_name: str,
        result: dict,
    ) -> dict:
        """
        Build an OpenAI-format tool result message for multi-turn tool calling.
        Called by LLMManager after executing a tool.
        """
        import json
        content = result.get("output") or result.get("error") or ""
        if isinstance(content, dict):
            content = json.dumps(content)
        elif not isinstance(content, str):
            content = str(content)

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        }
