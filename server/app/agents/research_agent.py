"""
ResearchAgent — Agentic web-search loop using Claude's native web_search_20260209,
web_fetch_20250910, and code_execution_20250825 tools, or Kimi's $web_search equivalent.

Dispatched via POST /chat/send when the message starts with "research:" or
contains research-intent keywords. Runs as a Celery background task.

Key design decisions:
- Does NOT use LLMManager.execute_with_tools() — the web_search_20260209 tool is a
  server-side Anthropic built-in, incompatible with the ToolExecutor pattern.
- Implements its own agentic loop (max 8 iterations) over AnthropicClient or KimiClient.
- Broadcasts step events (tool_call / tool_result) via _update_agent_task_step() so the
  mobile app can display live progress.
"""

import json
import logging
import os

from app.agents.base_agent import BaseAgent

logger = logging.getLogger("mezzofy.agents.research")

_MAX_ITERATIONS_DEFAULT = 8


class ResearchAgent(BaseAgent):
    """
    Web-search agentic loop agent.

    can_handle: task["agent"] == "research"
    execute:    Runs Claude (web_search_20260209 + web_fetch_20250910 + code_execution_20250825) or Kimi ($web_search) in a loop
                until end_turn/stop or max iterations reached.
    """

    def can_handle(self, task: dict) -> bool:
        return task.get("agent") == "research"

    async def execute(self, task: dict) -> dict:
        config = task.get("_config", {})
        provider = task.get("provider", "claude")
        use_kimi = provider == "kimi" and bool(os.environ.get("KIMI_API_KEY"))

        # Strip "research:" prefix if present
        raw_message = task.get("message", "")
        query = raw_message.removeprefix("research:").strip() or raw_message

        task_id = task.get("agent_task_id")
        messages = [{"role": "user", "content": query}]
        max_iter = config.get("agents", {}).get("max_research_iterations", _MAX_ITERATIONS_DEFAULT)
        final_text = ""

        logger.info(
            f"ResearchAgent.execute: provider={'kimi' if use_kimi else 'claude'} "
            f"query_len={len(query)} task_id={task_id}"
        )

        try:
            if use_kimi:
                final_text = await self._run_kimi_loop(messages, max_iter, task_id, config)
            else:
                final_text = await self._run_claude_loop(messages, max_iter, task_id, config)
        except Exception as exc:
            logger.error(f"ResearchAgent.execute failed: {exc}", exc_info=True)
            return self._err(f"Research failed: {exc}")

        return {
            "success": True,
            "content": final_text or "No result returned from web search.",
            "artifacts": [],
            "tools_called": ["web_search"],
            "agent_used": "research",
        }

    # ── Claude loop ───────────────────────────────────────────────────────────

    async def _run_claude_loop(
        self, messages: list[dict], max_iter: int, task_id: str | None, config: dict
    ) -> str:
        from app.llm.anthropic_client import AnthropicClient

        client = AnthropicClient(config)
        # Native Anthropic built-in tools — _format_tools() will pass through unchanged
        tools = [
            {"type": "web_search_20260209", "name": "web_search"},
            {"type": "web_fetch_20250910",  "name": "web_fetch"},
            {"type": "code_execution_20250825", "name": "code_execution"},
        ]
        final_text = ""

        for iteration in range(max_iter):
            response = await client.chat(messages, tools=tools)
            stop_reason = response.get("stop_reason", "")
            tool_calls = response.get("tool_calls") or []

            if stop_reason == "end_turn" or not tool_calls:
                final_text = response.get("content") or ""
                logger.debug(f"ResearchAgent Claude loop ended: iteration={iteration} reason={stop_reason}")
                break

            # Reconstruct assistant content blocks from normalized response
            content_blocks: list[dict] = []
            if response.get("content"):
                content_blocks.append({"type": "text", "text": response["content"]})
            for tc in tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"],
                })
            messages.append({"role": "assistant", "content": content_blocks})

            # Build tool results (Claude executes search itself; we send placeholder)
            tool_results: list[dict] = []
            for tc in tool_calls:
                q = tc["arguments"].get("query", "") if isinstance(tc.get("arguments"), dict) else ""
                await self._broadcast_step(task_id, "tool_call", f'Searching: "{q}"')
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": "Search executed by Claude.",
                })
                await self._broadcast_step(task_id, "tool_result", f'Results received for: "{q}"')

            messages.append({"role": "user", "content": tool_results})

        return final_text

    # ── Kimi loop ─────────────────────────────────────────────────────────────

    async def _run_kimi_loop(
        self, messages: list[dict], max_iter: int, task_id: str | None, config: dict
    ) -> str:
        from app.llm.kimi_client import KimiClient

        client = KimiClient(config)
        # Already in OpenAI function format — _format_tools() will pass through unchanged
        tools = [{
            "type": "function",
            "function": {
                "name": "$web_search",
                "description": "Search the web for current information",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }]
        final_text = ""

        for iteration in range(max_iter):
            response = await client.chat(messages, tools=tools)
            stop_reason = response.get("stop_reason", "stop")
            tool_calls = response.get("tool_calls") or []

            if stop_reason == "stop" or not tool_calls:
                final_text = response.get("content") or ""
                logger.debug(f"ResearchAgent Kimi loop ended: iteration={iteration} reason={stop_reason}")
                break

            # Append assistant message in OpenAI format
            messages.append({
                "role": "assistant",
                "content": response.get("content") or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                q = tc["arguments"].get("query", "") if isinstance(tc.get("arguments"), dict) else ""
                await self._broadcast_step(task_id, "tool_call", f'Kimi searching: "{q}"')
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": f'Web search executed for: "{q}". Results available.',
                })
                await self._broadcast_step(task_id, "tool_result", f'Kimi got results for: "{q}"')

        return final_text

    # ── Step broadcasting ─────────────────────────────────────────────────────

    async def _broadcast_step(
        self, task_id: str | None, step_type: str, message: str, progress: int = 50
    ) -> None:
        """Broadcast a step update. _update_agent_task_step manages its own DB session."""
        if not task_id:
            return
        try:
            from app.tasks.tasks import _update_agent_task_step
            await _update_agent_task_step(
                task_id,
                json.dumps({"type": step_type, "message": message}),
                progress,
            )
        except Exception as exc:
            logger.warning(f"ResearchAgent._broadcast_step failed (non-fatal): {exc}")
