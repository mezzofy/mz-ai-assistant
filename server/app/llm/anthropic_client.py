"""
AnthropicClient — Async Claude API client for the Mezzofy AI Assistant.

Uses anthropic.AsyncAnthropic for non-blocking I/O.
Supports multi-turn chat, tool/function calling, and streaming.

Config section: config["llm"]["claude"]
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Optional

import httpx

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

        self._client = anthropic.AsyncAnthropic(
            api_key=self._api_key,
            timeout=httpx.Timeout(
                connect=10.0,
                read=600.0,
                write=30.0,
                pool=10.0,
            ),
        )
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

        # Add Files API beta header when any message contains a document or image-via-file block
        def _is_files_api_block(b: dict) -> bool:
            if b.get("type") == "document":
                return True
            if b.get("type") == "image":
                src = b.get("source", {})
                return isinstance(src, dict) and src.get("type") == "file"
            return False

        _has_files_api = any(
            isinstance(m.get("content"), list)
            and any(isinstance(b, dict) and _is_files_api_block(b) for b in m["content"])
            for m in kwargs["messages"]
        )
        if _has_files_api:
            kwargs["extra_headers"] = {"anthropic-beta": "files-api-2025-04-14"}

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

        Native Anthropic built-in tools (e.g. web_search_20250305) are passed through
        unchanged — they only have "type" and "name" keys, not "description"/"parameters".
        """
        result = []
        for t in tools:
            # Native Anthropic built-in tool — pass through unchanged
            if "type" in t and t.get("type") != "function":
                result.append(t)
            else:
                result.append({
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                })
        return result

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

    # ── Server-Side Tools + Agent Skills support ──────────────────────────────

    async def chat_with_server_tools(
        self,
        messages: list,
        server_tools: list = None,
        client_tools: list = None,
        betas: list = None,
        container: dict = None,
        system: str = None,
        max_tokens: int = 8192,
    ) -> dict:
        """
        Extended chat method supporting Anthropic server-side tools and Agent Skills.

        Server tools (Anthropic executes — no local implementation needed):
          - web_search:      {"type": "web_search_20260209", "name": "web_search"}
          - web_fetch:       {"type": "web_fetch_20250910",  "name": "web_fetch"}
          - code_execution:  {"type": "code_execution_20250825", "name": "code_execution"}
          - memory:          {"type": "memory", "name": "memory"}

        Agent Skills (via container + betas):
          betas = ["code-execution-2025-08-25", "skills-2025-10-02"]
          container = {"skills": [{"type": "anthropic", "skill_id": "pptx", "version": "latest"}]}

        Returns:
          {
            content: [...],          # full content blocks
            stop_reason: str,        # "end_turn" | "pause_turn" | "tool_use"
            container_id: str|None,  # for continuing Skills sessions
            text: str,               # extracted text blocks joined
            file_ids: list[str],     # file_ids from Skills output
            tool_uses: list[dict],   # client tool_use blocks
            server_tool_uses: list[dict],  # server_tool_use blocks
            usage: dict,             # input/output tokens
          }
        """
        # Build tools list — server tools + client tools combined
        tools = []
        if server_tools:
            tools.extend(server_tools)
        if client_tools:
            tools.extend(client_tools)

        # Build request params
        params = {
            "model":      self._model,
            "max_tokens": max_tokens,
            "messages":   self._sanitize_messages(messages),
            "tools":      tools if tools else None,
        }
        if system:
            params["system"] = system
        if container:
            params["container"] = container

        # Use beta client if betas specified
        if betas:
            response = await self._client.beta.messages.create(
                **{k: v for k, v in params.items() if v is not None},
                betas=betas,
            )
        else:
            response = await self._client.messages.create(
                **{k: v for k, v in params.items() if v is not None},
            )

        return self._parse_extended_response(response)

    def _parse_extended_response(self, response) -> dict:
        """
        Parse response handling all content block types:
          - text blocks
          - tool_use blocks (client tools Claude wants to call)
          - server_tool_use blocks (web_search, web_fetch executing)
          - web_search_tool_result blocks
          - code_execution_result blocks
          - document/file blocks (from Skills)
        """
        text_parts = []
        file_ids = []
        tool_uses = []
        server_tool_uses = []
        container_id = getattr(response, "container", None)
        if container_id:
            container_id = getattr(container_id, "id", None)

        for block in response.content:
            block_type = getattr(block, "type", "")

            if block_type == "text":
                text_parts.append(block.text)

            elif block_type == "tool_use":
                # Client tool call — we need to execute locally
                tool_uses.append({
                    "id":    block.id,
                    "name":  block.name,
                    "input": block.input,
                })

            elif block_type == "server_tool_use":
                # Anthropic is executing this — just track it
                server_tool_uses.append({
                    "id":   block.id,
                    "name": block.name,
                    "input": getattr(block, "input", {}),
                })

            elif block_type in ("document", "file"):
                # File produced by a Skill
                fid = getattr(block, "file_id", None)
                if fid:
                    file_ids.append(fid)

            # web_search_tool_result and code_execution_result are
            # handled server-side — they appear in content but
            # we don't need to act on them locally

        return {
            "content":          response.content,
            "stop_reason":      response.stop_reason,
            "container_id":     container_id,
            "text":             "\n".join(text_parts),
            "file_ids":         file_ids,
            "tool_uses":        tool_uses,
            "server_tool_uses": server_tool_uses,
            "usage": {
                "input_tokens":  response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
