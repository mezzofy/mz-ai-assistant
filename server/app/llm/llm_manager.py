"""
LLMManager — Central orchestrator for Claude + Kimi LLM backends.

Responsibilities:
  - Routes requests: Chinese content → Kimi, everything else → Claude
  - Manages the agentic tool-calling loop (≤5 iterations)
  - Auto-failover: if primary model fails, retry on other
  - Tracks token usage per model/department/user → llm_usage table
  - Builds department-aware system prompts

Called by:
  - Chat API (Phase 5): mobile user messages via REST/WebSocket
  - Agent workflows (Phase 4): agents call execute_with_tools() directly
  - Scheduler / Webhook tasks (Phase 6): automated background tasks

Config section: config["llm"]
"""

import asyncio
import logging
import re
import unicodedata
from typing import Optional

from app.llm.anthropic_client import AnthropicClient
from app.llm.kimi_client import KimiClient
from app.tools.tool_executor import ToolExecutor

logger = logging.getLogger("mezzofy.llm.manager")

# ── Module-level singleton ─────────────────────────────────────────────────────

_manager: Optional["LLMManager"] = None


def init(config: dict) -> None:
    """Initialize the module-level LLMManager singleton. Call once at startup."""
    global _manager
    _manager = LLMManager(config)
    logger.info("LLMManager singleton initialized")


def get() -> "LLMManager":
    """Return the singleton LLMManager instance."""
    if _manager is None:
        raise RuntimeError(
            "LLMManager not initialized — call llm_manager.init(config) first"
        )
    return _manager

# Maximum tool-calling loop iterations
MAX_TOOL_ITERATIONS = 5

# System prompt template — filled with department/role/source at runtime
_SYSTEM_PROMPT_TEMPLATE = """You are the Mezzofy AI Assistant helping the {department} team.

You have access to tools for:
- Sending emails via Outlook (Microsoft Graph API)
- Creating/reading calendar events in Outlook
- Posting messages to MS Teams channels
- Generating PDFs, slide decks, and Word documents
- Searching the web and LinkedIn for company and contact research
- Querying Mezzofy's internal data (products, pricing, features, case studies)
- Managing the CRM / sales lead database
- Querying financial, support ticket, and operational databases
- Processing and analyzing images, audio, and video files

Department context: {department}
User role: {role}
Task source: {source}

Be professional, concise, and action-oriented. When generating customer-facing content, use Mezzofy brand voice (confident, friendly, professional). When sending emails via Outlook, always confirm with the user before sending unless they explicitly said "auto send" or this is a scheduled/webhook task (auto-send is allowed for automated workflows).

When delivering scheduled report results, format output clearly for MS Teams with headings and attach generated files."""


class LLMManager:
    """
    Orchestrates Claude and Kimi LLM calls with routing, tool use, and failover.
    """

    def __init__(self, config: dict):
        self.config = config
        self.claude = AnthropicClient(config)
        self.kimi = KimiClient(config)
        self.tool_executor = ToolExecutor(config)
        logger.info("LLMManager ready (Claude + Kimi)")

    # ── Public API ────────────────────────────────────────────────────────────

    def select_model(self, message: str, context: Optional[dict] = None) -> object:
        """
        Select the appropriate LLM backend for this request.

        Routing rules (in order):
          1. Chinese characters in message → Kimi
          2. APAC / Chinese market signals in context → Kimi
          3. Everything else → Claude

        Args:
            message: The user's message text.
            context: Optional task context dict (may include "department", "source", etc.)

        Returns:
            AnthropicClient or KimiClient instance.
        """
        if self._contains_chinese(message):
            logger.debug("select_model: Chinese content detected → Kimi")
            return self.kimi

        if context and self._is_chinese_market_task(message, context):
            logger.debug("select_model: APAC/Chinese market task detected → Kimi")
            return self.kimi

        logger.debug("select_model: default → Claude")
        return self.claude

    async def chat(
        self,
        messages: list[dict],
        task_context: Optional[dict] = None,
        stream: bool = False,
    ) -> dict:
        """
        Simple single-turn or multi-turn chat without tool calling.

        Args:
            messages: Conversation history.
            task_context: {department, role, source} for system prompt.
            stream: If True, returns streaming response (for WebSocket).

        Returns:
            Normalized response dict from the selected model.
        """
        system = self._build_system_prompt(task_context)
        last_message = messages[-1]["content"] if messages else ""
        model = self.select_model(last_message, task_context)

        try:
            return await model.chat(messages, system=system)
        except Exception as primary_err:
            logger.warning(
                f"LLMManager.chat: primary model ({model.model_name}) failed: {primary_err} — failing over"
            )
            fallback = self.kimi if model is self.claude else self.claude
            return await fallback.chat(messages, system=system)

    async def execute_with_tools(
        self,
        task: dict,
        tool_names: Optional[list[str]] = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> dict:
        """
        Run the agentic tool-calling loop.

        Selects model, calls it with tool definitions, executes any requested tools,
        feeds results back, and repeats until the model returns a final answer
        or the max iterations limit is reached.

        Args:
            task: Task dict containing at minimum:
                  - "message": str — user's request
                  - "messages": list[dict] — conversation history (optional)
                  - "department": str — for system prompt
                  - "role": str — user role
                  - "source": str — "mobile" | "scheduler" | "webhook"
                  - "user_id": str — for usage tracking
            tool_names: Subset of tool names to expose. None = all registered tools.
            max_iterations: Hard cap on tool-calling rounds. Default: 5.

        Returns:
            {
                "success": bool,
                "content": str,         # Final LLM response text
                "iterations": int,      # Number of tool-calling rounds used
                "tools_called": list,   # Names of tools invoked
                "usage": {              # Aggregate token usage
                    "input_tokens": int,
                    "output_tokens": int,
                    "model": str,
                },
            }
        """
        message = task.get("message", "")
        model = self.select_model(message, task)
        system = self._build_system_prompt(task)

        # Build initial message list
        history = list(task.get("messages", []))
        if not history or history[-1].get("content") != message:
            history.append({"role": "user", "content": message})

        # Get tool definitions
        all_tool_defs = self.tool_executor.get_all_definitions()
        if tool_names:
            tool_defs = [t for t in all_tool_defs if t["name"] in tool_names]
        else:
            tool_defs = all_tool_defs

        total_usage = {"input_tokens": 0, "output_tokens": 0}
        tools_called: list[str] = []
        iterations = 0
        used_model = model

        for i in range(max_iterations):
            iterations = i + 1

            try:
                response = await model.chat(history, tools=tool_defs, system=system)
            except Exception as primary_err:
                logger.warning(
                    f"LLMManager tool loop: primary model failed on iteration {iterations}: "
                    f"{primary_err} — failing over"
                )
                try:
                    fallback = self.kimi if model is self.claude else self.claude
                    response = await fallback.chat(history, tools=tool_defs, system=system)
                    used_model = fallback
                except Exception as fallback_err:
                    logger.error(f"LLMManager tool loop: both models failed: {fallback_err}")
                    return {
                        "success": False,
                        "content": "Both AI models are currently unavailable. Please try again shortly.",
                        "iterations": iterations,
                        "tools_called": tools_called,
                        "usage": {**total_usage, "model": model.model_name},
                    }

            # Accumulate token usage
            usage = response.get("usage", {})
            total_usage["input_tokens"] += usage.get("input_tokens", 0)
            total_usage["output_tokens"] += usage.get("output_tokens", 0)

            # No tool calls → final answer
            if not response.get("tool_calls"):
                # Track usage asynchronously (non-blocking, non-fatal)
                asyncio.create_task(self._track_usage(
                    model_name=used_model.model_name,
                    department=task.get("department", "unknown"),
                    user_id=task.get("user_id", "system"),
                    input_tokens=total_usage["input_tokens"],
                    output_tokens=total_usage["output_tokens"],
                ))
                return {
                    "success": True,
                    "content": response["content"],
                    "iterations": iterations,
                    "tools_called": tools_called,
                    "usage": {**total_usage, "model": used_model.model_name},
                }

            # Execute requested tools
            tool_calls = response["tool_calls"]
            tool_results = []

            for tc in tool_calls:
                tool_name = tc["name"]
                tools_called.append(tool_name)
                logger.info(f"LLMManager: executing tool '{tool_name}' (iteration {iterations})")

                try:
                    result = await self.tool_executor.execute(tool_name, **tc["arguments"])
                except Exception as e:
                    logger.error(f"Tool '{tool_name}' raised exception: {e}")
                    result = {"success": False, "error": str(e)}

                tool_results.append((tc, result))

            # Append assistant message with tool calls + tool result messages to history
            history = self._append_tool_exchange(
                model=used_model,
                history=history,
                tool_calls=tool_calls,
                tool_results=tool_results,
            )

        # Reached max iterations without final answer
        logger.warning(
            f"LLMManager: reached max iterations ({max_iterations}) — returning partial answer"
        )
        asyncio.create_task(self._track_usage(
            model_name=used_model.model_name,
            department=task.get("department", "unknown"),
            user_id=task.get("user_id", "system"),
            input_tokens=total_usage["input_tokens"],
            output_tokens=total_usage["output_tokens"],
        ))
        return {
            "success": True,
            "content": f"I completed {len(tools_called)} steps but reached the maximum action limit. "
                       f"Tools used: {', '.join(tools_called) if tools_called else 'none'}. "
                       f"Please narrow your request or try again.",
            "iterations": iterations,
            "tools_called": tools_called,
            "usage": {**total_usage, "model": used_model.model_name},
        }

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream_response(self, task: dict):
        """
        Stream a response token by token for WebSocket delivery.

        Yields str chunks. Does NOT support tool calling (streaming + tools
        are handled in Phase 5 via the WebSocket handler).
        """
        message = task.get("message", "")
        model = self.select_model(message, task)
        system = self._build_system_prompt(task)
        messages = task.get("messages", [{"role": "user", "content": message}])

        try:
            async for chunk in model.stream_chat(messages, system=system):
                yield chunk
        except Exception as e:
            logger.error(f"LLMManager.stream_response failed: {e}")
            yield f"\n[Error: streaming failed — {e}]"

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_system_prompt(self, task: Optional[dict]) -> str:
        """Build department-aware system prompt from task context."""
        if not task:
            return _SYSTEM_PROMPT_TEMPLATE.format(
                department="General", role="user", source="mobile"
            )
        return _SYSTEM_PROMPT_TEMPLATE.format(
            department=task.get("department", "General"),
            role=task.get("role", "user"),
            source=task.get("source", "mobile"),
        )

    def _contains_chinese(self, text: str) -> bool:
        """
        Return True if the text contains Chinese characters
        (Simplified or Traditional CJK Unified Ideographs).
        """
        for char in text:
            name = unicodedata.name(char, "")
            if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
                return True
        # Also check Unicode ranges directly
        return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", text))

    def _is_chinese_market_task(self, message: str, context: dict) -> bool:
        """
        Return True if the task is oriented toward Chinese market / APAC research.
        Checked when no Chinese characters are present in the message.
        """
        apac_signals = {
            "china", "chinese market", "mainland", "apac", "asia pacific",
            "singapore", "malaysia", "taiwan", "hong kong", "mandarin",
            "中国", "亚太", "新加坡"
        }
        msg_lower = message.lower()
        if any(signal in msg_lower for signal in apac_signals):
            return True

        # Check context for APAC routing signals
        department = context.get("department", "").lower()
        return department in ("apac", "china", "asia")

    def _append_tool_exchange(
        self,
        model: object,
        history: list[dict],
        tool_calls: list[dict],
        tool_results: list[tuple],
    ) -> list[dict]:
        """
        Append the assistant's tool calls and tool results to the conversation history.

        Handles format differences between Anthropic (content blocks) and OpenAI (tool_calls array).
        """
        if model is self.claude:
            # Anthropic format: assistant message with tool_use content blocks
            assistant_content = []
            for tc in tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"],
                })
            history.append({"role": "assistant", "content": assistant_content})

            # Tool results: single user message with tool_result blocks
            result_content = []
            for tc, result in tool_results:
                content = result.get("output") or result.get("error") or ""
                if not isinstance(content, str):
                    import json
                    content = json.dumps(content)
                result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": content,
                })
            history.append({"role": "user", "content": result_content})

        else:
            # OpenAI/Kimi format: assistant message with tool_calls array
            openai_tool_calls = []
            import json
            for tc in tool_calls:
                openai_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"]),
                    },
                })
            history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": openai_tool_calls,
            })

            # Individual tool result messages
            for tc, result in tool_results:
                content = result.get("output") or result.get("error") or ""
                if not isinstance(content, str):
                    content = json.dumps(content)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["name"],
                    "content": content,
                })

        return history

    async def _track_usage(
        self,
        model_name: str,
        department: str,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Insert token usage record into llm_usage table.
        Non-fatal — failures are logged but do not affect the response.
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            sql = """
                INSERT INTO llm_usage
                    (model, department, user_id, input_tokens, output_tokens)
                VALUES
                    (:model, :department, :user_id, :input_tokens, :output_tokens)
            """
            async with AsyncSessionLocal() as session:
                await session.execute(text(sql), {
                    "model": model_name,
                    "department": department,
                    "user_id": user_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })
                await session.commit()
        except Exception as e:
            logger.warning(f"_track_usage failed (non-fatal): {e}")
