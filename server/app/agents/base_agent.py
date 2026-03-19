"""
BaseAgent — Abstract base class for all Mezzofy department agents.

All department agents (Finance, Sales, Marketing, Support, Management)
inherit from BaseAgent. Agents are responsible for:
  - Selecting appropriate skills for the task
  - Orchestrating multi-step tool workflows via LLMManager
  - Delivering results to the right channel (mobile app, Teams, Outlook)

Task sources:
  - "mobile"    — User-initiated via mobile app (REST/WebSocket)
  - "scheduler" — Celery Beat cron job (delivers to Teams + Outlook)
  - "webhook"   — External event from Mezzofy product (delivers to Teams + push)

v2.0 additions:
  - Agent identity: self.agent_id, self.agent_record (lazy-loaded from DB)
  - Delegation: delegate_task(), await_delegation()
  - Task logging: log_task_start/complete/failed() → agent_task_log table
  - Knowledge: _load_knowledge() — namespace-scoped RAG file loading
  - Skill introspection: requires_skill(), can_handle_with_delegation()
"""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.skills import skill_registry

logger = logging.getLogger("mezzofy.agents.base")

# Path to knowledge base root (relative to server/ directory)
_SERVER_ROOT = Path(__file__).parent.parent.parent  # server/
KNOWLEDGE_BASE_PATH = _SERVER_ROOT / "knowledge"


class BaseAgent(ABC):
    """
    Abstract base for all department agents.

    Subclasses must implement can_handle() and execute().
    Skills are loaded on demand via _load_skill().
    """

    def __init__(self, config: dict):
        self.config = config
        self._skills: dict = {}
        # v2.0: persistent identity fields (populated lazily by load_agent_record())
        self.agent_id: Optional[str] = None
        self.agent_record: Optional[dict] = None
        logger.debug(f"{self.__class__.__name__} initialized")

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def can_handle(self, task: dict) -> bool:
        """
        Return True if this agent can handle the given task.

        Checks task["department"] and/or intent keywords in task["message"].

        Args:
            task: Task dict with at least "message" and "department" keys.
        """

    @abstractmethod
    async def execute(self, task: dict) -> dict:
        """
        Run the agent's workflow for the given task.

        Args:
            task: {
                "message": str,            # User's request
                "messages": list[dict],    # Conversation history
                "department": str,         # User's department
                "role": str,               # User's role
                "source": str,             # "mobile" | "scheduler" | "webhook"
                "user_id": str,            # User ID (or "system" for automated)
                "permissions": list[str],  # Resolved permissions from RBAC
            }

        Returns:
            {
                "success": bool,
                "content": str,           # Text response
                "artifacts": list[dict],  # Generated files [{name, path, type}]
                "tools_called": list[str],
            }
        """

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _load_skill(self, skill_name: str) -> object:
        """
        Load a skill instance from the registry (lazy, cached per agent instance).

        Args:
            skill_name: Skill name (e.g., "linkedin_prospecting").

        Returns:
            Skill instance.

        Raises:
            ValueError: If skill not found in registry.
        """
        if skill_name not in self._skills:
            skill = skill_registry.get(skill_name)
            if skill is None:
                raise ValueError(f"Skill '{skill_name}' not found in registry")
            self._skills[skill_name] = skill
            logger.debug(f"{self.__class__.__name__}: loaded skill '{skill_name}'")
        return self._skills[skill_name]

    def _require_permission(self, task: dict, permission: str) -> None:
        """
        Check that the task context includes the required permission.

        For scheduler and webhook tasks, permission checks are bypassed
        (system-level operations have pre-authorized access).

        Args:
            task: Task dict containing "permissions" list and "source".
            permission: Required permission string (e.g., "email_send").

        Raises:
            PermissionError: If permission not granted.
        """
        source = task.get("source", "mobile")
        if source in ("scheduler", "webhook"):
            return  # System-level — always authorized

        permissions = task.get("permissions", [])
        if permission not in permissions:
            raise PermissionError(
                f"Action requires '{permission}' permission. "
                f"Contact your admin to request access."
            )

    def _is_automated(self, task: dict) -> bool:
        """Return True if this is a scheduler or webhook task (not mobile user)."""
        return task.get("source", "mobile") in ("scheduler", "webhook")

    async def _deliver_to_teams(self, channel: str, message: str, attachments: Optional[list] = None) -> dict:
        """
        Post a message (and optional file links) to a MS Teams channel.

        Used by scheduled and webhook workflows for automated delivery.
        """
        from app.tools.communication.teams_ops import TeamsOps
        teams = TeamsOps(self.config)
        return await teams.execute(
            "teams_post_message",
            channel=channel,
            message=message,
            attachments=attachments or [],
        )

    async def _send_email(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: Optional[list] = None,
    ) -> dict:
        """
        Send an email via Outlook (MS Graph API).

        Used by scheduled and webhook workflows for automated delivery.
        """
        from app.tools.communication.outlook_ops import OutlookOps
        outlook = OutlookOps(self.config)
        return await outlook.execute(
            "outlook_send_email",
            to=to,
            subject=subject,
            body=body,
            body_type="HTML",
            attachments=attachments or [],
        )

    async def _general_response(self, task: dict) -> dict:
        """
        General fallback — answer via LLM with full tool access.

        Used when the request doesn't match any department-specific workflow.
        Enables tools like create_txt, create_csv, create_pdf, send_email, etc.
        Conversation history is available for multi-turn tool use
        (e.g., LLM asks 'personal or shared?' → user replies → LLM calls tool).

        Note: task["messages"] is set by router._execute_with_instance() from
        task["conversation_history"] before dispatch reaches here.
        """
        from app.llm import llm_manager as llm_mod
        llm_result = await llm_mod.get().execute_with_tools(task)
        content = llm_result.get("content", "I'm here to help. What would you like to do?")
        tools_called = llm_result.get("tools_called", [])
        artifacts = llm_result.get("artifacts", [])
        return self._ok(content=content, tools_called=tools_called, artifacts=artifacts)

    def _ok(self, content: str, artifacts: Optional[list] = None, tools_called: Optional[list] = None) -> dict:
        """Build a successful agent response."""
        return {
            "success": True,
            "content": content,
            "artifacts": artifacts or [],
            "tools_called": tools_called or [],
        }

    def _err(self, message: str) -> dict:
        """Build an error agent response."""
        return {
            "success": False,
            "content": message,
            "artifacts": [],
            "tools_called": [],
        }

    # ── v2.0: Agent identity ──────────────────────────────────────────────────

    async def load_agent_record(self, agent_id: str) -> None:
        """
        Populate self.agent_id and self.agent_record from the agents DB table.

        Called lazily before any operation that needs the agent's skill manifest
        or memory namespace. Safe to call multiple times — cached after first load.
        """
        if self.agent_record is not None:
            return  # Already loaded
        try:
            from app.agents.agent_registry import agent_registry
            if agent_registry.is_loaded():
                self.agent_record = agent_registry.get(agent_id)
                self.agent_id = agent_id
            else:
                # Fallback: direct DB lookup
                from app.core.database import AsyncSessionLocal
                from sqlalchemy import text
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        text("SELECT * FROM agents WHERE id = :id"),
                        {"id": agent_id},
                    )
                    row = result.fetchone()
                    if row:
                        import json as _json
                        row_dict = dict(row._mapping)
                        for field in ("skills", "tools_allowed"):
                            val = row_dict.get(field, [])
                            if isinstance(val, str):
                                try:
                                    row_dict[field] = _json.loads(val)
                                except Exception:
                                    row_dict[field] = []
                        self.agent_record = row_dict
                        self.agent_id = agent_id
        except Exception as e:
            logger.warning(
                f"{self.__class__.__name__}.load_agent_record({agent_id!r}) failed: {e}"
            )

    # ── v2.0: Skill introspection ─────────────────────────────────────────────

    def requires_skill(self, skill_name: str) -> bool:
        """Return True if skill_name is in this agent's skills list (from DB record)."""
        if self.agent_record is None:
            return False
        return skill_name in self.agent_record.get("skills", [])

    def can_handle_with_delegation(
        self, task: dict, agent_registry_instance
    ) -> tuple[bool, list[str]]:
        """
        Check if this agent can handle a task, possibly by delegating parts.

        Returns:
            (can_handle: bool, delegation_needed_to: list[agent_id])
        """
        if self.can_handle(task):
            return (True, [])

        # Check if another agent can handle via skill matching
        if agent_registry_instance and agent_registry_instance.is_loaded():
            task_type = task.get("task_type", "")
            if task_type:
                capable = agent_registry_instance.find_capable_agent(task_type)
                if capable:
                    return (True, [capable["id"]])
        return (False, [])

    # ── v2.0: Task logging → agent_task_log ──────────────────────────────────

    async def log_task_start(
        self, task: dict, parent_task_id: Optional[str] = None
    ) -> str:
        """
        Insert a new row into agent_task_log with status='running'.

        Returns the new task UUID string, or empty string on failure.
        """
        try:
            import uuid as _uuid
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text
            task_id = str(_uuid.uuid4())
            agent_id = self.agent_id or f"agent_{self.__class__.__name__.lower().replace('agent', '')}"
            triggered_by = task.get("user_id", "")
            source = task.get("source", "mobile")
            task_type = task.get("task_type") or task.get("agent") or ""
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("""
                        INSERT INTO agent_task_log
                            (id, agent_id, parent_task_id, requested_by_agent_id,
                             triggered_by_user_id, source, task_type,
                             task_input, status, started_at)
                        VALUES
                            (:id, :agent_id, :parent_task_id, :requested_by_agent_id,
                             :triggered_by_user_id, :source, :task_type,
                             :task_input::jsonb, 'running', NOW())
                    """),
                    {
                        "id": task_id,
                        "agent_id": agent_id,
                        "parent_task_id": parent_task_id,
                        "requested_by_agent_id": task.get("_requesting_agent_id"),
                        "triggered_by_user_id": triggered_by,
                        "source": source,
                        "task_type": task_type,
                        "task_input": __import__("json").dumps({
                            k: v for k, v in task.items()
                            if k not in ("_config", "_progress_callback") and isinstance(v, (str, int, float, bool, list, dict, type(None)))
                        })[:4000],
                    },
                )
                await db.commit()
            return task_id
        except Exception as e:
            logger.warning(f"{self.__class__.__name__}.log_task_start failed: {e}")
            return ""

    async def log_task_complete(self, task_id: str, result: dict) -> None:
        """Update agent_task_log row: status=completed, result_summary, duration_ms."""
        if not task_id:
            return
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text
            summary = result.get("content", "")[:2000]
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("""
                        UPDATE agent_task_log
                        SET status = 'completed',
                            result_summary = :summary,
                            completed_at = NOW(),
                            duration_ms = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER * 1000
                        WHERE id = :task_id
                    """),
                    {"task_id": task_id, "summary": summary},
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"{self.__class__.__name__}.log_task_complete failed: {e}")

    async def log_task_failed(self, task_id: str, error: str) -> None:
        """Update agent_task_log row: status=failed, error_message."""
        if not task_id:
            return
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("""
                        UPDATE agent_task_log
                        SET status = 'failed',
                            error_message = :error,
                            completed_at = NOW(),
                            duration_ms = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER * 1000
                        WHERE id = :task_id
                    """),
                    {"task_id": task_id, "error": str(error)[:2000]},
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"{self.__class__.__name__}.log_task_failed failed: {e}")

    # ── v2.0: Inter-agent delegation ──────────────────────────────────────────

    async def delegate_task(
        self, target_agent_id: str, task: dict, parent_task_id: str
    ) -> dict:
        """
        Request work from another specialist agent via Celery.

        Non-blocking by default — the calling agent continues its own work.
        Use await_delegation() if the result is needed before proceeding.

        Returns:
            { task_id: str, agent_id: str, status: "queued" }
        """
        try:
            from app.agents.agent_registry import agent_registry as _registry
            from app.tasks.celery_app import celery_app
            import uuid as _uuid

            # Verify target is valid and spawnable
            if _registry.is_loaded():
                target_rec = _registry.get(target_agent_id)
                if not target_rec.get("can_be_spawned", True):
                    raise ValueError(
                        f"Agent '{target_agent_id}' cannot be spawned (can_be_spawned=False)"
                    )
                if not target_rec.get("is_active", True):
                    raise ValueError(f"Agent '{target_agent_id}' is not active")

            # Build delegation task payload
            delegated_task = {
                **{k: v for k, v in task.items()
                   if k not in ("_config", "_progress_callback")},
                "_requesting_agent_id": self.agent_id,
                "_parent_task_id": parent_task_id,
            }

            # Insert queued log row
            import uuid as _uuid2
            task_id = str(_uuid2.uuid4())
            try:
                from app.core.database import AsyncSessionLocal
                from sqlalchemy import text
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text("""
                            INSERT INTO agent_task_log
                                (id, agent_id, parent_task_id, requested_by_agent_id,
                                 triggered_by_user_id, source, status, queued_at)
                            VALUES
                                (:id, :agent_id, :parent_task_id, :requesting_agent_id,
                                 :user_id, 'agent_delegation', 'queued', NOW())
                        """),
                        {
                            "id": task_id,
                            "agent_id": target_agent_id,
                            "parent_task_id": parent_task_id,
                            "requesting_agent_id": self.agent_id,
                            "user_id": task.get("user_id", ""),
                        },
                    )
                    await db.commit()
            except Exception as log_err:
                logger.warning(f"delegate_task: failed to log queued row: {log_err}")
                task_id = str(_uuid2.uuid4())  # still proceed

            # Enqueue the Celery task
            delegated_task["_agent_task_log_id"] = task_id
            delegated_task["agent"] = target_agent_id.replace("agent_", "")
            celery_app.send_task(
                "app.tasks.tasks.process_delegated_agent_task",
                kwargs={
                    "task_data": delegated_task,
                    "agent_id": target_agent_id,
                    "parent_task_id": parent_task_id,
                    "requested_by_agent_id": self.agent_id or "",
                },
            )
            logger.info(
                f"{self.__class__.__name__}.delegate_task: "
                f"→ {target_agent_id} task_id={task_id}"
            )
            return {"task_id": task_id, "agent_id": target_agent_id, "status": "queued"}
        except Exception as e:
            logger.error(f"{self.__class__.__name__}.delegate_task failed: {e}")
            return {"task_id": "", "agent_id": target_agent_id, "status": "error", "error": str(e)}

    async def await_delegation(
        self, task_id: str, timeout_seconds: int = 300
    ) -> dict:
        """
        Block until a delegated sub-task completes (or times out).

        Polls agent_task_log every 5 seconds up to timeout_seconds.
        Returns the result_summary and result_artifacts from agent_task_log.
        """
        import asyncio as _asyncio
        elapsed = 0
        poll_interval = 5
        while elapsed < timeout_seconds:
            try:
                from app.core.database import AsyncSessionLocal
                from sqlalchemy import text
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        text("""
                            SELECT status, result_summary, result_artifacts, error_message
                            FROM agent_task_log
                            WHERE id = :task_id
                        """),
                        {"task_id": task_id},
                    )
                    row = result.fetchone()
                    if row:
                        status = row.status
                        if status == "completed":
                            return {
                                "success": True,
                                "status": "completed",
                                "result_summary": row.result_summary or "",
                                "result_artifacts": row.result_artifacts or [],
                            }
                        if status == "failed":
                            return {
                                "success": False,
                                "status": "failed",
                                "error": row.error_message or "Sub-task failed",
                                "result_summary": "",
                                "result_artifacts": [],
                            }
            except Exception as e:
                logger.warning(f"await_delegation poll error: {e}")
            await _asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {
            "success": False,
            "status": "timeout",
            "error": f"Delegation timed out after {timeout_seconds}s",
            "result_summary": "",
            "result_artifacts": [],
        }

    # ── v2.0: Knowledge base loading ─────────────────────────────────────────

    def _load_knowledge(self) -> list[Path]:
        """
        Return paths to RAG knowledge files for this agent only.

        Loads from:
          - knowledge/{memory_namespace}/ — agent-specific files
          - knowledge/shared/             — cross-agent shared files

        No cross-namespace access: a finance agent cannot load sales knowledge.

        Returns:
            List of Path objects for .md, .txt, and .pdf files.
        """
        namespace = None
        if self.agent_record:
            namespace = self.agent_record.get("memory_namespace")
        if not namespace:
            # Derive from class name as fallback (e.g. FinanceAgent → "finance")
            cls_name = self.__class__.__name__.lower()
            namespace = cls_name.replace("agent", "").strip("_") or "shared"

        agent_dir = KNOWLEDGE_BASE_PATH / namespace
        shared_dir = KNOWLEDGE_BASE_PATH / "shared"

        files: list[Path] = []
        for d in (agent_dir, shared_dir):
            if d.exists() and d.is_dir():
                for pattern in ("*.md", "*.txt", "*.pdf"):
                    files.extend(d.glob(pattern))
        return files
