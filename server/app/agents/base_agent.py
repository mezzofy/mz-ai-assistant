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
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.skills import skill_registry

logger = logging.getLogger("mezzofy.agents.base")


class BaseAgent(ABC):
    """
    Abstract base for all department agents.

    Subclasses must implement can_handle() and execute().
    Skills are loaded on demand via _load_skill().
    """

    def __init__(self, config: dict):
        self.config = config
        self._skills: dict = {}
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
