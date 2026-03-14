"""
AgentRegistry — Maps department names to agent classes.

Used by the Router (Phase 5) to select the appropriate agent
for incoming tasks based on department and access rights.

Routing model:
  1. Department → Agent is always 1:1 (primary routing, no exceptions).
  2. Unknown departments: cross-department routing is only allowed for users
     with "cross_department_access" permission or admin/executive/management role.
  3. All known-department users always stay in their department's agent,
     which handles general requests via its fallback _general_response() path.
"""

import logging

from app.agents.finance_agent import FinanceAgent
from app.agents.hr_agent import HRAgent
from app.agents.management_agent import ManagementAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.sales_agent import SalesAgent
from app.agents.support_agent import SupportAgent
from app.agents.research_agent import ResearchAgent
from app.agents.developer_agent import DeveloperAgent
from app.agents.scheduler_agent import SchedulerAgent

logger = logging.getLogger("mezzofy.agents.registry")

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
