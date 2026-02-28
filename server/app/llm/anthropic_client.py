"""
AnthropicClient — Async Claude API client for the Mezzofy AI Assistant.

Uses anthropic.AsyncAnthropic for non-blocking I/O.
Supports multi-turn chat, tool/function calling, and streaming.

Config section: config["llm"]["claude"]
"""

import logging
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger("mezzofy.llm.anthropic")


class AnthropicClient:
    """
    Async wrapper around the Anthropic Claude API.

    All calls are non-blocking. Tool definitions follow Anthropic's
    native format (type/name/description/input_schema).
    """

    def __init__(self, config: dict):
        """
        Args:
            config: Full config dict. Reads from config["llm"]["claude"].
        """
        import anthropic

        claude_cfg = config.get("llm", {}).get("claude", {})
        self._api_key: str = claude_cfg.get("api_key", "")
        self._model: str = claude_cfg.get("model", "claude-sonnet-4-6")
        self._max_tokens: int = int(claude_cfg.get("max_tokens", 4096))
        self._temperature: float = float(claude_cfg.get("temperature", 0.7))

        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        logger.info(f"AnthropicClient ready (model={self._model})")

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
        Send a chat request to Claude.

        Args:
            messages: Conversation history in Anthropic format.
                      [{"role": "user"|"assistant", "content": str | list}, ...]
            tools: Optional list of tool definitions in Anthropic function-calling format.
            system: System prompt string. Overrides default if provided.
            max_tokens: Override max_tokens for this request.

        Returns:
            {
                "content": str,             # Text response (if no tool calls)
                "tool_calls": [...] | None, # Tool calls requested by model
                "stop_reason": str,         # "end_turn" | "tool_use" | "max_tokens"
                "usage": {"input_tokens": int, "output_tokens": int},
                "model": str,
            }
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            # Convert from ToolExecutor format to Anthropic tool format
            kwargs["tools"] = self._format_tools(tools)

        try:
            response = await self._client.messages.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"AnthropicClient.chat failed: {e}")
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
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"AnthropicClient.stream_chat failed: {e}")
            raise

    # ── Private helpers ───────────────────────────────────────────────────────

    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """
        Convert ToolExecutor definition format to Anthropic tool format.

        ToolExecutor format:
            {"name": "...", "description": "...", "parameters": {...JSON Schema...}}

        Anthropic format:
            {"name": "...", "description": "...", "input_schema": {...JSON Schema...}}
        """
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]

    def _parse_response(self, response) -> dict:
        """
        Normalize Anthropic API response to internal format.

        Returns dict with content, tool_calls, stop_reason, usage, model.
        """
        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,  # dict
                })

        return {
            "content": content_text,
            "tool_calls": tool_calls if tool_calls else None,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "model": response.model,
        }

    def _build_tool_result_message(
        self,
        tool_call_id: str,
        tool_name: str,
        result: dict,
    ) -> dict:
        """
        Build an Anthropic-format tool result message for multi-turn tool calling.
        Called by LLMManager after executing a tool.
        """
        content = result.get("output") or result.get("error") or ""
        if isinstance(content, dict):
            import json
            content = json.dumps(content)
        elif not isinstance(content, str):
            content = str(content)

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": content,
                }
            ],
        }
