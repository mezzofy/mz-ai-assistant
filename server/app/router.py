"""
Router — intent classification and agent dispatch.

Every normalized task dict flows through here after the Gateway.
The Router selects the correct department agent and executes it.

Source-specific routing:
  - webhook   → route by event type mapping table
  - scheduler → route by job's pre-configured agent field
  - teams     → route by @mention context + user department (same as mobile)
  - mobile    → agent_registry.get_agent_for_task() classification

Returns agent execute() result dict with at minimum:
  {success, content, artifacts, tools_called, agent_used}
"""

import logging
from typing import Optional

from app.agents.agent_registry import get_agent_for_task, AGENT_MAP

logger = logging.getLogger("mezzofy.router")

# Webhook event keyword → agent name
_WEBHOOK_EVENT_AGENT: dict[str, str] = {
    "customer_signed_up":    "sales",
    "customer_churned":      "management",
    "order_completed":       "finance",
    "support_ticket_created": "support",
    "feature_released":      "marketing",
}


async def route_request(task: dict) -> dict:
    """
    Route a normalized task dict to the correct agent and execute it.

    Args:
        task: Normalized task dict from gateway / chat handler. Must contain:
            source      — "mobile" | "webhook" | "scheduler" | "teams"
            message     — str (user text or empty for webhooks)
            department  — str (user's dept, or "" for webhooks)
            _config     — full app config dict (injected by chat.py)

    Returns:
        Agent result dict:
            success      — bool
            content      — str  (main response text)
            artifacts    — list (generated file records)
            tools_called — list
            agent_used   — str
    """
    source = task.get("source", "mobile")
    config = task.get("_config", {})

    try:
        if source == "webhook":
            return await _route_webhook(task, config)
        if source == "scheduler":
            return await _route_scheduler(task, config)
        # mobile + teams use the same classification path
        return await _route_mobile(task, config)

    except Exception as exc:
        logger.error(f"Router error (source={source}): {exc}", exc_info=True)
        return _err(f"Routing error: {exc}")


# ── Source-specific dispatchers ───────────────────────────────────────────────

async def _route_webhook(task: dict, config: dict) -> dict:
    """Route webhook events by event keyword → agent name table."""
    event = task.get("event", "")
    agent_name: Optional[str] = None

    for keyword, name in _WEBHOOK_EVENT_AGENT.items():
        if keyword in event:
            agent_name = name
            break

    if not agent_name:
        logger.warning(f"No agent mapping for webhook event: {event!r}")
        return _err(f"No handler registered for webhook event: {event}")

    return await _execute_by_name(agent_name, task, config)


async def _route_scheduler(task: dict, config: dict) -> dict:
    """Route scheduler tasks using the job's pre-configured agent name."""
    agent_name = task.get("agent") or task.get("department", "")
    if not agent_name:
        logger.warning("Scheduler task missing 'agent' field")
        return _err("Scheduler task missing agent configuration")
    return await _execute_by_name(agent_name, task, config)


async def _route_mobile(task: dict, config: dict) -> dict:
    """Route mobile/Teams requests via agent_registry keyword classification."""
    agent = get_agent_for_task(task, config)

    if agent is None:
        # No agent matched — ask user to clarify
        logger.info(
            "No agent matched — returning clarification prompt. "
            f"message={task.get('message', '')[:80]!r}"
        )
        return {
            "success": True,
            "content": (
                "I'm not sure which department this request is for. "
                "Could you clarify whether this is a finance, sales, marketing, "
                "support, or management task?"
            ),
            "artifacts": [],
            "tools_called": [],
            "agent_used": "none",
        }

    return await _execute_with_instance(agent, task)


# ── Execution helpers ─────────────────────────────────────────────────────────

async def _execute_by_name(agent_name: str, task: dict, config: dict) -> dict:
    """Instantiate an agent by name string and execute the task."""
    AgentClass = AGENT_MAP.get(agent_name.lower())
    if AgentClass is None:
        logger.error(f"Unknown agent name: {agent_name!r}")
        return _err(f"Unknown agent: {agent_name}")

    agent = AgentClass(config)
    return await _execute_with_instance(agent, task)


async def _execute_with_instance(agent, task: dict) -> dict:
    """Execute task with an already-constructed agent instance."""
    agent_label = agent.__class__.__name__.replace("Agent", "").lower()
    logger.info(
        f"Dispatching to {agent.__class__.__name__} "
        f"(source={task.get('source', 'mobile')}, "
        f"message={task.get('message', '')[:60]!r})"
    )
    result = await agent.execute(task)
    result.setdefault("agent_used", agent_label)
    return result


def _err(detail: str) -> dict:
    return {
        "success": False,
        "content": detail,
        "artifacts": [],
        "tools_called": [],
        "agent_used": "none",
    }
