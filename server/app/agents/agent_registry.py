"""
AgentRegistry — Maps department names to agent classes.

Used by the Router (Phase 5) to select the appropriate agent
for incoming tasks based on department and message intent.
"""

import logging
from typing import Optional

from app.agents.finance_agent import FinanceAgent
from app.agents.management_agent import ManagementAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.sales_agent import SalesAgent
from app.agents.support_agent import SupportAgent

logger = logging.getLogger("mezzofy.agents.registry")

# Department → Agent class mapping
AGENT_MAP = {
    "finance": FinanceAgent,
    "sales": SalesAgent,
    "marketing": MarketingAgent,
    "support": SupportAgent,
    "management": ManagementAgent,
}

# All agent classes (for can_handle routing)
_ALL_AGENTS = list(AGENT_MAP.values())


def get_agent_for_task(task: dict, config: dict):
    """
    Select and instantiate the best agent for the given task.

    Selection order:
    1. User's department provides a strong hint
    2. Each agent's can_handle() method confirms or overrides
    3. Management Agent handles cross-department requests
    4. Falls back to SalesAgent as default

    Args:
        task: Task dict with "department" and "message" keys.
        config: Full app config dict.

    Returns:
        Instantiated agent, or None if no match.
    """
    department = task.get("department", "").lower()

    # Direct department match
    if department in AGENT_MAP:
        agent_cls = AGENT_MAP[department]
        agent = agent_cls(config)
        if agent.can_handle(task):
            logger.debug(f"AgentRegistry: department match → {agent_cls.__name__}")
            return agent

    # Keyword-based can_handle fallback across all agents
    for agent_cls in _ALL_AGENTS:
        agent = agent_cls(config)
        if agent.can_handle(task):
            logger.debug(f"AgentRegistry: keyword match → {agent_cls.__name__}")
            return agent

    # Default: Management for cross-department, Sales for everything else
    default_cls = ManagementAgent if department == "management" else SalesAgent
    logger.debug(f"AgentRegistry: default fallback → {default_cls.__name__}")
    return default_cls(config)


def get_all_agent_names() -> list[str]:
    """Return list of all registered department names."""
    return list(AGENT_MAP.keys())
