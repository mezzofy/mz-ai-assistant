"""
AgentRegistry — Maps department names to agent classes + DB-backed agent records.

Two layers:
  1. AgentRegistry class — DB-backed singleton. Loaded at app startup via
     AgentRegistry.load(). Provides lookup by ID, department, and skill.
     Used by ManagementAgent for orchestration and by BaseAgent for delegation.

  2. Module-level functions (backward-compat) — get_agent_for_task(), AGENT_MAP.
     Used by Router, Celery tasks, and all code written before v2.0.

Routing model:
  1. Department → Agent is always 1:1 (primary routing, no exceptions).
  2. Unknown departments: cross-department routing is only allowed for users
     with "cross_department_access" permission or admin/executive/management role.
  3. All known-department users always stay in their department's agent,
     which handles general requests via its fallback _general_response() path.
"""

import json
import logging
from typing import Optional

from app.agents.finance_agent import FinanceAgent
from app.agents.hr_agent import HRAgent
from app.agents.management_agent import ManagementAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.sales_agent import SalesAgent
from app.agents.support_agent import SupportAgent
from app.agents.research_agent import ResearchAgent
from app.agents.developer_agent import DeveloperAgent
from app.agents.scheduler_agent import SchedulerAgent
from app.agents.legal_agent import LegalAgent

logger = logging.getLogger("mezzofy.agents.registry")


# ── DB-backed AgentRegistry class (v2.0) ──────────────────────────────────────

class AgentRegistry:
    """
    Central registry for all active AI agents.

    Loaded from the `agents` DB table at application startup via load().
    Provides lookup by agent_id, department, and required skill.
    Used by ManagementAgent for orchestration and by BaseAgent for delegation.

    Usage:
        # At startup (main.py lifespan):
        await agent_registry.load()

        # At runtime:
        record = agent_registry.get("agent_sales")
        agents = agent_registry.find_by_skill("code_generation")
    """

    def __init__(self):
        # Keyed by agent_id string, e.g. "agent_sales"
        self._agents: dict[str, dict] = {}
        self._loaded: bool = False

    async def load(self) -> None:
        """
        Load all agents from the `agents` DB table into memory.

        Safe to call multiple times — overwrites the in-memory cache each time.
        No-ops gracefully if the agents table does not yet exist (pre-migration).
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT * FROM agents WHERE is_active = TRUE ORDER BY id")
                )
                rows = result.fetchall()
                self._agents = {}
                for row in rows:
                    row_dict = dict(row._mapping)
                    # Parse JSONB fields (may arrive as str or already parsed)
                    for field in ("skills", "tools_allowed"):
                        val = row_dict.get(field, [])
                        if isinstance(val, str):
                            try:
                                row_dict[field] = json.loads(val)
                            except Exception:
                                row_dict[field] = []
                    self._agents[row_dict["id"]] = row_dict
                self._loaded = True
                logger.info(
                    f"AgentRegistry loaded {len(self._agents)} agents: "
                    f"{list(self._agents.keys())}"
                )
        except Exception as e:
            # Table may not exist yet (pre-migration) — warn but don't crash
            logger.warning(
                f"AgentRegistry.load() failed — agents table may not exist yet. "
                f"Delegation and orchestration will be unavailable. Error: {e}"
            )
            self._loaded = False

    def get(self, agent_id: str) -> dict:
        """Return agent record dict. Raises KeyError if not found."""
        if agent_id not in self._agents:
            raise KeyError(f"Agent '{agent_id}' not found in registry")
        return self._agents[agent_id]

    def get_by_department(self, department: str) -> Optional[dict]:
        """Return agent record for the given department, or None."""
        dept = department.lower()
        for rec in self._agents.values():
            if rec.get("department", "").lower() == dept:
                return rec
        return None

    def find_by_skill(self, skill_name: str) -> list[dict]:
        """Return all active agents that have skill_name in their skills list."""
        return [
            rec for rec in self._agents.values()
            if skill_name in rec.get("skills", [])
        ]

    def find_capable_agent(self, task_type: str) -> Optional[dict]:
        """
        Find the best agent for a given task type.
        Tries exact skill name match first, then department keyword match.
        Returns agent record or None.
        """
        # 1. Exact skill name match
        matches = self.find_by_skill(task_type)
        if matches:
            return matches[0]
        # 2. Department keyword match (fallback)
        task_lower = task_type.lower()
        for rec in self._agents.values():
            if task_lower in rec.get("department", "").lower():
                return rec
        return None

    def all_active(self) -> list[dict]:
        """Return all agents where is_active=True (all loaded records)."""
        return list(self._agents.values())

    def get_orchestrator(self) -> Optional[dict]:
        """Return the agent where is_orchestrator=True (Management Agent)."""
        for rec in self._agents.values():
            if rec.get("is_orchestrator"):
                return rec
        return None

    def is_loaded(self) -> bool:
        """Return True if load() has been called successfully."""
        return self._loaded


# Module-level singleton — initialized at app startup
agent_registry = AgentRegistry()


# ── Department → Agent class mapping (backward-compat, v1.x) ─────────────────

# Department → Agent class mapping
AGENT_MAP = {
    "finance": FinanceAgent,
    "hr": HRAgent,
    "sales": SalesAgent,
    "marketing": MarketingAgent,
    "support": SupportAgent,
    "management": ManagementAgent,
    "research": ResearchAgent,
    "developer": DeveloperAgent,
    "scheduler": SchedulerAgent,
    "legal": LegalAgent,
    "agent_legal": LegalAgent,  # Support explicit agent_override routing
}

# All agent classes (for cross-department keyword fallback)
_ALL_AGENTS = list(AGENT_MAP.values())

# Permission string granting cross-department routing access
_CROSS_DEPT_PERMISSION = "cross_department_access"
# Roles that always have cross-department access (no explicit permission needed)
_CROSS_DEPT_ROLES = {"admin", "executive", "management"}


def get_agent_for_task(task: dict, config: dict):
    """
    Select and instantiate the correct agent for the given task.

    Selection logic:
    1. User's department → always use that department's agent (primary routing).
       Every known department maps directly to exactly one agent — no exceptions.
    2. Unknown department + cross_department_access permission → keyword fallback
       across all agents to find the best match.
    3. Unknown department, no cross-dept permission → SalesAgent default.

    Cross-department routing (step 2) is only activated for:
      - Users with "cross_department_access" in permissions
      - Users with role: admin, executive, or management

    Args:
        task: Task dict with "department", "role", "permissions", and "message" keys.
        config: Full app config dict.

    Returns:
        Instantiated agent (never None — always has a fallback).
    """
    department = task.get("department", "").lower()
    role = task.get("role", "").lower()
    permissions = task.get("permissions", [])

    # 1. Direct department → agent routing (primary path for all known departments)
    if department in AGENT_MAP:
        agent_cls = AGENT_MAP[department]
        logger.debug(f"AgentRegistry: department routing → {agent_cls.__name__} (dept={department!r})")
        return agent_cls(config)

    # 2. Unknown department: check if user has cross-department access
    can_cross_dept = (
        _CROSS_DEPT_PERMISSION in permissions
        or role in _CROSS_DEPT_ROLES
    )

    if can_cross_dept:
        for agent_cls in _ALL_AGENTS:
            agent = agent_cls(config)
            if agent.can_handle(task):
                logger.debug(
                    f"AgentRegistry: cross-dept keyword routing → {agent_cls.__name__} "
                    f"(role={role!r}, perm=cross_department_access)"
                )
                return agent

    # 3. Default fallback for unknown departments
    logger.debug(
        f"AgentRegistry: default fallback → SalesAgent "
        f"(dept={department!r} unknown, cross_dept={'yes' if can_cross_dept else 'no'})"
    )
    return SalesAgent(config)


def get_all_agent_names() -> list[str]:
    """Return list of all registered department names."""
    return list(AGENT_MAP.keys())
