"""
DeveloperAgent — Runs `claude --output-format stream-json --dangerously-skip-permissions -p <query>`
as a headless subprocess and streams structured JSON output as task step events.

Dispatched via POST /chat/send when the message starts with "developer:" or contains
developer-intent keywords. Runs as a Celery background task.

Prerequisites:
  - Claude Code CLI installed on the server:
    npm install -g @anthropic-ai/claude-code
  - ANTHROPIC_API_KEY set in environment

Stream-JSON event types handled:
  assistant  → "thinking" step (first 300 chars of text block)
  tool_use   → "tool_call" step (name + input[:150])
  tool_result → "tool_result" step (content[:200])
  result     → "done" step + captures final result text
  error      → "error" step
"""

import asyncio
import json
import logging
import os

from app.agents.base_agent import BaseAgent

logger = logging.getLogger("mezzofy.agents.developer")

_DEFAULT_WORK_DIR = "~/mezzofy-workspace"
_DEFAULT_TIMEOUT = 300  # seconds


class DeveloperAgent(BaseAgent):
    """
    Claude Code headless subprocess agent.

    can_handle: task["agent"] == "developer"
    execute:    Runs `claude --output-format stream-json --dangerously-skip-permissions -p <query>`
                in a work directory, streams JSON events, and returns the final result.
    """

    def can_handle(self, task: dict) -> bool:
        return task.get("agent") == "developer"

    async def execute(self, task: dict) -> dict:
        config = task.get("_config", {})
        agents_cfg = config.get("agents", {})

        # Strip "developer:" prefix if present
        raw_message = task.get("message", "")
        query = raw_message.removeprefix("developer:").strip() or raw_message

        task_id = task.get("agent_task_id")
        work_dir = os.path.expanduser(
            task.get("work_dir")
            or agents_cfg.get("developer_work_dir")
            or _DEFAULT_WORK_DIR
        )
        timeout = int(agents_cfg.get("max_developer_timeout", _DEFAULT_TIMEOUT))

        os.makedirs(work_dir, exist_ok=True)
        logger.info(
            f"DeveloperAgent.execute: work_dir={work_dir!r} "
            f"query_len={len(query)} task_id={task_id} timeout={timeout}s"
        )

        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "-p", query,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env={**os.environ, "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "")},
            )
        except FileNotFoundError:
            msg = (
                "Claude Code CLI not found. "
                "Install with: npm install -g @anthropic-ai/claude-code"
            )
            logger.error(f"DeveloperAgent: {msg}")
            return self._err(msg)
        except Exception as exc:
            logger.error(f"DeveloperAgent: failed to start subprocess: {exc}", exc_info=True)
            return self._err(f"Failed to start developer agent: {exc}")

        final_result = ""

        try:
            async with asyncio.timeout(timeout):
                async for raw_line in process.stdout:
                    line = raw_line.decode(errors="replace").strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type")

                    if etype == "assistant":
                        for block in event.get("message", {}).get("content", []):
                            if block.get("type") == "text":
                                snippet = block["text"][:300]
                                await self._broadcast_step(task_id, "thinking", snippet)

                    elif etype == "tool_use":
                        tool_name = event.get("name", "")
                        tool_input = json.dumps(event.get("input", {}))[:150]
                        await self._broadcast_step(task_id, "tool_call", f"{tool_name}: {tool_input}")

                    elif etype == "tool_result":
                        content = str(event.get("content", ""))[:200]
                        await self._broadcast_step(task_id, "tool_result", content)

                    elif etype == "result":
                        final_result = event.get("result", "")
                        snippet = final_result[:300]
                        await self._broadcast_step(task_id, "done", snippet)

                    elif etype == "error":
                        err_msg = event.get("error", "Unknown error from Claude Code")
                        logger.warning(f"DeveloperAgent stream error event: {err_msg}")
                        await self._broadcast_step(task_id, "error", err_msg)

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()  # Reap zombie — must wait after kill to release OS resources
            logger.warning(f"DeveloperAgent timed out after {timeout}s (task_id={task_id})")
            return self._err(f"Developer agent timed out after {timeout}s.")

        await process.wait()

        if process.returncode != 0:
            stderr_bytes = await process.stderr.read()
            stderr_text = stderr_bytes.decode(errors="replace")[:500]
            logger.warning(
                f"DeveloperAgent subprocess exited with code {process.returncode}: {stderr_text}"
            )

        return {
            "success": True,
            "content": final_result or "Task complete.",
            "artifacts": [],
            "tools_called": ["claude_code"],
            "agent_used": "developer",
        }

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
            logger.warning(f"DeveloperAgent._broadcast_step failed (non-fatal): {exc}")
