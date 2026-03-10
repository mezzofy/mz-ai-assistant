"""
AnthropicClient — Async Claude API client for the Mezzofy AI Assistant.

Uses anthropic.AsyncAnthropic for non-blocking I/O.
Supports multi-turn chat, tool/function calling, and streaming.

Config section: config["llm"]["claude"]
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger("mezzofy.llm.anthropic")


class AnthropicClient:
    """
    Async wrapper around the Anthropic Claude API.

    All calls are non-blocking. Tool definitions follow Anthropic's
    native format (type/name/description/input_schema).
    """

    _BASE_SYSTEM_PROMPT = (
        "You are a helpful AI assistant. Be concise and direct. "
        "Format responses clearly using markdown where appropriate. "
        "Think step by step for complex tasks."
    )

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
        self._temperature: float = float(claude_cfg.get("temperature", 0.5))

        self._client = anthropic.AsyncAnthropic(api_key=self._api_key, timeout=60.0)
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
        effective_system = system or self._BASE_SYSTEM_PROMPT

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": self._sanitize_messages(messages),
        }

        if effective_system:
            kwargs["system"] = effective_system

        if tools:
            # Convert from ToolExecutor format to Anthropic tool format
            kwargs["tools"] = self._format_tools(tools)

        # Add Files API beta header when any message contains a document block
        _has_files_api = any(
            isinstance(m.get("content"), list)
            and any(
                isinstance(b, dict) and b.get("type") == "document"
                for b in m["content"]
            )
            for m in kwargs["messages"]
        )
        if _has_files_api:
            kwargs["betas"] = ["files-api-2025-04-14"]

        _RETRY_STATUS = {429, 500, 529}
        # 429 rate-limit: wait for the token-per-minute bucket to refill (30–60s).
        # 500/529 server errors and timeouts: short exponential backoff is fine.
        _RATE_LIMIT_DELAYS = [30, 60, 60]
        _SERVER_ERROR_DELAYS = [1, 2, 4]

        last_exc: Exception | None = None
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.messages.create(**kwargs)
                return self._parse_response(response)
            except Exception as e:
                status = getattr(e, "status_code", None)
                is_rate_limit = status == 429
                is_retryable = (
                    status in _RETRY_STATUS
                    or "timeout" in str(e).lower()
                    or "connection" in str(e).lower()
                )
                delays = _RATE_LIMIT_DELAYS if is_rate_limit else _SERVER_ERROR_DELAYS
                if is_retryable and attempt <= len(delays):
                    delay = delays[attempt - 1]
                    logger.warning(
                        f"AnthropicClient.chat attempt {attempt} failed "
                        f"(status={status}): {e} — retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    last_exc = e
                    continue
                logger.error(f"AnthropicClient.chat failed (attempt {attempt}): {e}")
                raise
        raise last_exc  # unreachable guard

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
            "messages": self._sanitize_messages(messages),
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

    @staticmethod
    def _sanitize_messages(messages: list[dict]) -> list[dict]:
        """
        Strip fields not accepted by the Anthropic API (e.g. 'timestamp' added
        by session_manager). Only 'role' and 'content' are passed through.
        """
        _ALLOWED = {"role", "content"}
        return [
            {k: v for k, v in msg.items() if k in _ALLOWED}
            for msg in messages
        ]

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
