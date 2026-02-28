"""
Webhook Celery Tasks — async processing of inbound webhook events.

Each task:
  1. Updates the webhook_events record (status → processing)
  2. Builds a task dict and routes to the appropriate agent
  3. Delivers results to configured channels (Teams, email, push)
  4. Updates the webhook_events record (status → completed/failed)

Called by: app.webhooks.webhooks (after returning 200 to the external service)
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger("mezzofy.tasks.webhook")

# ── Mezzofy event → agent mapping (mirrors router.py) ─────────────────────────

_MEZZOFY_EVENT_AGENT = {
    "customer_signed_up": "sales",
    "customer_churned": "management",
    "order_completed": "finance",
    "support_ticket_created": "support",
    "feature_released": "marketing",
}

# ── Mezzofy webhook task ───────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="app.tasks.webhook_tasks.handle_mezzofy_event")
def handle_mezzofy_event(self, event_id: str, event_type: str, payload: dict):
    """
    Process a Mezzofy platform webhook event.

    Routes to the correct department agent based on event_type, then delivers
    results to Teams channel + email if specified in payload.

    Args:
        event_id:   UUID of the webhook_events DB record.
        event_type: e.g. "customer_signed_up", "order_completed"
        payload:    Parsed event data dict from the webhook body.
    """
    try:
        asyncio.run(_run_mezzofy_event(event_id, event_type, payload))
    except Exception as exc:
        logger.error(f"Mezzofy webhook task failed (event_id={event_id}): {exc}", exc_info=True)
        # Update event record to failed
        try:
            asyncio.run(_mark_event_failed(event_id, str(exc)))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_mezzofy_event(event_id: str, event_type: str, payload: dict):
    """Core async logic for Mezzofy event handling."""
    from app.core.config import get_config
    from app.core.database import AsyncSessionLocal
    from app.agents.agent_registry import get_agent_for_task
    from sqlalchemy import text

    config = get_config()
    agent_name = _MEZZOFY_EVENT_AGENT.get(event_type)

    if not agent_name:
        logger.warning(f"No agent mapping for Mezzofy event: {event_type!r}")
        await _mark_event_completed(event_id, {"skipped": f"No handler for {event_type!r}"})
        return

    # Build task dict for agent
    task = _build_webhook_task(agent_name, event_type, payload, config)

    # Mark as processing
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE webhook_events SET status = 'processing' WHERE id = :id"),
            {"id": event_id},
        )
        await db.commit()

    # Run agent
    agent = get_agent_for_task(task, config)
    if agent is None:
        logger.warning(f"Agent {agent_name!r} not found for Mezzofy event {event_type}")
        await _mark_event_failed(event_id, f"Agent {agent_name!r} not available")
        return

    result = await agent.execute(task)

    # Deliver results if configured
    deliver_to = payload.get("deliver_to", {})
    if not deliver_to:
        # Default delivery: notify the relevant Teams channel
        deliver_to = {"teams_channel": agent_name}
    await _deliver_results_async(result, deliver_to, config)

    # Mark event completed
    await _mark_event_completed(event_id, {
        "agent_used": result.get("agent_used", agent_name),
        "content_preview": (result.get("content", "") or "")[:200],
    })

    logger.info(f"Mezzofy event {event_type!r} processed successfully (event_id={event_id})")


# ── Teams webhook task ─────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="app.tasks.webhook_tasks.handle_teams_mention")
def handle_teams_mention(self, event_id: str, payload: dict):
    """
    Process a Microsoft Teams @mention webhook event.

    Routes the Teams message through the full Gateway → Router → Agent pipeline,
    then posts the response back to the originating Teams channel.

    Args:
        event_id: UUID of the webhook_events DB record.
        payload:  Parsed Teams webhook payload dict.
    """
    try:
        asyncio.run(_run_teams_mention(event_id, payload))
    except Exception as exc:
        logger.error(f"Teams webhook task failed (event_id={event_id}): {exc}", exc_info=True)
        try:
            asyncio.run(_mark_event_failed(event_id, str(exc)))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_teams_mention(event_id: str, payload: dict):
    """Core async logic for Teams @mention handling."""
    from app.core.config import get_config
    from app.agents.agent_registry import get_agent_for_task
    from sqlalchemy import text

    config = get_config()

    # Extract message text (strip @MezzofyAI mention)
    raw_text = payload.get("text", "")
    message = _strip_mention(raw_text)

    from_user = payload.get("from", {})
    channel_data = payload.get("channelData", {})
    channel_id = (channel_data.get("channel") or {}).get("id", "")
    team_id = (channel_data.get("team") or {}).get("id", "")

    # Mark as processing
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE webhook_events SET status = 'processing' WHERE id = :id"),
            {"id": event_id},
        )
        await db.commit()

    # Build task — Teams messages route as "management" by default, agent auto-detected
    task = {
        "message": message,
        "input_type": "text",
        "source": "webhook",
        "user_id": from_user.get("id", "teams_user"),
        "department": "management",  # Bot responds to any department
        "role": "user",
        "permissions": [],
        "session_id": None,
        "attachments": [],
        "conversation_history": [],
        "_config": config,
        "teams_channel_id": channel_id,
        "teams_team_id": team_id,
    }

    # Route to best agent
    agent = get_agent_for_task(task, config)
    if agent is None:
        # Fallback: use management agent
        from app.agents.agent_registry import AGENT_MAP
        agent = AGENT_MAP.get("management")

    result = {} if agent is None else await agent.execute(task)
    content = result.get("content", "I processed your request. Check the relevant channel for updates.")

    # Post reply to Teams channel
    if channel_id:
        try:
            from app.tools.communication.teams_ops import TeamsOps
            teams = TeamsOps(config)
            await teams.execute(
                "post_message",
                team_id=team_id,
                channel_id=channel_id,
                message=content,
            )
        except Exception as e:
            logger.warning(f"Failed to post Teams reply: {e}")

    await _mark_event_completed(event_id, {
        "agent_used": result.get("agent_used", "unknown"),
        "content_preview": content[:200],
    })
    logger.info(f"Teams mention processed (event_id={event_id})")


# ── Custom webhook task ────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="app.tasks.webhook_tasks.handle_custom_event")
def handle_custom_event(self, event_id: str, source: str, payload: dict):
    """
    Process a custom webhook event (Zapier, GitHub, Stripe, etc.)

    Routes based on payload content using the management agent by default.

    Args:
        event_id: UUID of the webhook_events DB record.
        source:   Custom source identifier (e.g. "zapier", "github", "stripe").
        payload:  Parsed webhook payload dict.
    """
    try:
        asyncio.run(_run_custom_event(event_id, source, payload))
    except Exception as exc:
        logger.error(f"Custom webhook task failed (event_id={event_id}): {exc}", exc_info=True)
        try:
            asyncio.run(_mark_event_failed(event_id, str(exc)))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_custom_event(event_id: str, source: str, payload: dict):
    """Core async logic for custom webhook events."""
    from app.core.config import get_config
    from app.agents.agent_registry import AGENT_MAP
    from sqlalchemy import text

    config = get_config()

    # Build a natural language message from the payload for the LLM
    import json
    message = (
        f"Custom webhook received from {source!r}. "
        f"Process and summarize this event:\n{json.dumps(payload, indent=2)[:2000]}"
    )

    task = {
        "message": message,
        "input_type": "text",
        "source": "webhook",
        "user_id": "webhook_system",
        "department": "management",
        "role": "admin",
        "permissions": ["all"],
        "session_id": None,
        "attachments": [],
        "conversation_history": [],
        "_config": config,
    }

    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE webhook_events SET status = 'processing' WHERE id = :id"),
            {"id": event_id},
        )
        await db.commit()

    agent = AGENT_MAP.get("management")
    result = {} if agent is None else await agent.execute(task)

    await _mark_event_completed(event_id, {
        "content_preview": (result.get("content", "") or "")[:200],
    })
    logger.info(f"Custom webhook {source!r} processed (event_id={event_id})")


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _build_webhook_task(agent_name: str, event_type: str, payload: dict, config: dict) -> dict:
    """Build a standard task dict from a Mezzofy webhook payload."""
    import json
    data = payload.get("data", payload)
    message = (
        f"Webhook event received: {event_type!r}. "
        f"Process this event and take appropriate action. "
        f"Event data: {json.dumps(data, default=str)[:1500]}"
    )
    return {
        "message": message,
        "input_type": "text",
        "source": "webhook",
        "event_type": event_type,
        "user_id": "webhook_system",
        "department": _agent_to_department(agent_name),
        "role": "admin",
        "permissions": ["all"],
        "session_id": None,
        "attachments": [],
        "conversation_history": [],
        "_config": config,
    }


def _agent_to_department(agent_name: str) -> str:
    """Map agent name to department string."""
    return {
        "sales": "sales",
        "marketing": "marketing",
        "finance": "finance",
        "support": "support",
        "management": "management",
    }.get(agent_name, "management")


def _strip_mention(text: str) -> str:
    """Remove @MezzofyAI and similar bot mentions from Teams message text."""
    import re
    text = re.sub(r"<at>[^<]*</at>", "", text).strip()
    return text or "Hello, how can you help me?"


async def _deliver_results_async(result: dict, deliver_to: dict, config: dict):
    """Deliver agent results to configured channels (Teams, email, push)."""
    content = result.get("content", "")
    artifacts = result.get("artifacts", [])
    title = result.get("title", "Mezzofy AI Report")

    if deliver_to.get("teams_channel"):
        try:
            from app.tools.communication.teams_ops import TeamsOps
            teams = TeamsOps(config)
            msg = content[:5000]  # Teams message limit
            await teams.execute("post_message", channel=deliver_to["teams_channel"], message=msg)
        except Exception as e:
            logger.warning(f"Teams delivery failed: {e}")

    if deliver_to.get("email"):
        try:
            from app.tools.communication.outlook_ops import OutlookOps
            outlook = OutlookOps(config)
            recipients = deliver_to["email"]
            if isinstance(recipients, str):
                recipients = [recipients]
            for recipient in recipients:
                attachment_paths = [a.get("path") for a in artifacts if a.get("path")]
                await outlook.execute(
                    "send_email",
                    to=recipient,
                    subject=f"[Mezzofy AI] {title}",
                    body=content,
                    attachments=attachment_paths,
                )
        except Exception as e:
            logger.warning(f"Email delivery failed: {e}")

    if deliver_to.get("push_user_id"):
        try:
            from app.tools.communication.push_ops import PushOps
            push = PushOps(config)
            await push.execute(
                "send_push",
                user_id=deliver_to["push_user_id"],
                title="Task Complete",
                body=(content or "")[:100],
            )
        except Exception as e:
            logger.warning(f"Push delivery failed: {e}")


async def _mark_event_completed(event_id: str, result_data: dict):
    """Update webhook_events record to completed status."""
    import json
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE webhook_events "
                "SET status = 'completed', result = :result, processed_at = NOW() "
                "WHERE id = :id"
            ),
            {"id": event_id, "result": json.dumps(result_data)},
        )
        await db.commit()


async def _mark_event_failed(event_id: str, error_msg: str):
    """Update webhook_events record to failed status."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE webhook_events "
                "SET status = 'failed', error_msg = :err, processed_at = NOW() "
                "WHERE id = :id"
            ),
            {"id": event_id, "err": error_msg[:500]},
        )
        await db.commit()
