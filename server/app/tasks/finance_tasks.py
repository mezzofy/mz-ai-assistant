"""
Finance Celery tasks — scheduled financial operations.

Tasks:
    check_overdue_invoices()       — Daily 8:30AM SGT: flag newly overdue invoices,
                                     post summary to #finance Teams channel
    ar_ap_weekly_summary()         — Monday 9AM SGT: AR/AP aging weekly summary
                                     to finance manager
    month_close_reminder()         — 25th of month 9AM SGT: remind finance manager
                                     to complete month-end close
    gst_filing_reminder()          — 15th of Jan/Apr/Jul/Oct: GST F5 filing reminder
    generate_monthly_statements()  — 2nd of month 9:30AM SGT: auto-generate P&L,
                                     Balance Sheet, Cash Flow for previous month

All schedules are in UTC. Conversion: 9AM SGT = 01:00 UTC, 8:30AM SGT = 00:30 UTC.
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger("mezzofy.tasks.finance")


@celery_app.task(name="app.tasks.finance_tasks.check_overdue_invoices")
def check_overdue_invoices():
    """
    Daily 8:30AM SGT: check for newly overdue invoices and notify finance team.

    Queries fin_invoices WHERE due_date < TODAY AND status = 'sent'
    AND outstanding_amount > 0, then posts a summary to the #finance Teams channel.
    """
    logger.info("Finance task: checking overdue invoices")
    try:
        asyncio.run(_check_overdue_invoices_async())
    except Exception as e:
        logger.error(f"check_overdue_invoices failed: {e}")
        raise


@celery_app.task(name="app.tasks.finance_tasks.ar_ap_weekly_summary")
def ar_ap_weekly_summary():
    """
    Monday 9AM SGT: generate AR and AP aging summary and deliver to finance manager.

    Produces two aging reports (AR + AP) with bucket breakdown (current, 1-30,
    31-60, 61-90, 90+ days) and posts summary to Teams + emails finance manager.
    """
    logger.info("Finance task: generating weekly AR/AP summary")
    try:
        asyncio.run(_ar_ap_weekly_summary_async())
    except Exception as e:
        logger.error(f"ar_ap_weekly_summary failed: {e}")
        raise


@celery_app.task(name="app.tasks.finance_tasks.month_close_reminder")
def month_close_reminder():
    """
    25th of every month 9AM SGT: send month-end close reminder to finance manager.

    Posts the standard close checklist to Teams #finance and emails the
    finance manager with action items to complete before month-end.
    """
    logger.info("Finance task: sending month-end close reminder")
    try:
        asyncio.run(_month_close_reminder_async())
    except Exception as e:
        logger.error(f"month_close_reminder failed: {e}")
        raise


@celery_app.task(name="app.tasks.finance_tasks.gst_filing_reminder")
def gst_filing_reminder():
    """
    15th of Jan/Apr/Jul/Oct 9AM SGT: send GST F5 filing reminder.

    Reminds the finance manager of the upcoming GST F5 submission deadline
    and provides a checklist of items to verify before filing with IRAS.
    """
    logger.info("Finance task: sending GST filing reminder")
    try:
        asyncio.run(_gst_filing_reminder_async())
    except Exception as e:
        logger.error(f"gst_filing_reminder failed: {e}")
        raise


@celery_app.task(name="app.tasks.finance_tasks.generate_monthly_statements")
def generate_monthly_statements():
    """
    2nd of every month 9:30AM SGT: auto-generate monthly financial statements.

    Generates P&L, Balance Sheet, and Cash Flow statement for the previous
    calendar month. Delivers to finance manager via Teams and email.
    """
    logger.info("Finance task: generating monthly financial statements")
    try:
        asyncio.run(_generate_monthly_statements_async())
    except Exception as e:
        logger.error(f"generate_monthly_statements failed: {e}")
        raise


# ── Async implementations ─────────────────────────────────────────────────────

async def _check_overdue_invoices_async():
    """Async body: route overdue invoice check through FinanceAgent."""
    from app.core.config import load_config
    from app.agents.finance_agent import FinanceAgent

    config = load_config()
    agent = FinanceAgent(config)
    task = {
        "agent": "finance",
        "source": "scheduler",
        "department": "finance",
        "user_id": "system",
        "event": "daily_overdue_check",
        "message": "Check for newly overdue invoices and notify the finance team",
        "deliver_to": {"teams_channel": "finance"},
        "db": None,
        "session_id": "scheduler",
    }
    result = await agent.handle_ar_followup(task)
    logger.info(f"check_overdue_invoices completed: {result.get('content', '')[:200]}")


async def _ar_ap_weekly_summary_async():
    """Async body: route weekly AR/AP summary through FinanceAgent."""
    from app.core.config import load_config
    from app.agents.finance_agent import FinanceAgent

    config = load_config()
    agent = FinanceAgent(config)
    task = {
        "agent": "finance",
        "source": "scheduler",
        "department": "finance",
        "user_id": "system",
        "event": "ar_ap_weekly_summary",
        "message": "Generate weekly AR and AP aging summary report",
        "deliver_to": {"teams_channel": "finance"},
        "db": None,
        "session_id": "scheduler",
    }
    result = await agent._ar_ap_summary_workflow(task)
    logger.info(f"ar_ap_weekly_summary completed: {result.get('content', '')[:200]}")


async def _month_close_reminder_async():
    """Async body: send month-end close reminder through FinanceAgent."""
    from app.core.config import load_config
    from app.agents.finance_agent import FinanceAgent

    config = load_config()
    agent = FinanceAgent(config)
    task = {
        "agent": "finance",
        "source": "scheduler",
        "department": "finance",
        "user_id": "system",
        "event": "month_close_reminder",
        "message": "Send month-end close reminder to finance manager",
        "deliver_to": {"teams_channel": "finance"},
        "db": None,
        "session_id": "scheduler",
    }
    result = await agent._month_close_reminder_workflow(task)
    logger.info(f"month_close_reminder completed: {result.get('content', '')[:200]}")


async def _gst_filing_reminder_async():
    """Async body: send GST filing reminder through FinanceAgent."""
    from app.core.config import load_config
    from app.agents.finance_agent import FinanceAgent

    config = load_config()
    agent = FinanceAgent(config)
    task = {
        "agent": "finance",
        "source": "scheduler",
        "department": "finance",
        "user_id": "system",
        "event": "gst_filing_reminder",
        "message": "Send GST F5 filing reminder — quarter-end filing due",
        "deliver_to": {"teams_channel": "finance"},
        "db": None,
        "session_id": "scheduler",
    }
    result = await agent.handle_tax_preparation(task)
    logger.info(f"gst_filing_reminder completed: {result.get('content', '')[:200]}")


async def _generate_monthly_statements_async():
    """Async body: generate monthly financial statements through FinanceAgent."""
    from app.core.config import load_config
    from app.agents.finance_agent import FinanceAgent

    config = load_config()
    agent = FinanceAgent(config)
    task = {
        "agent": "finance",
        "source": "scheduler",
        "department": "finance",
        "user_id": "system",
        "event": "monthly_statements",
        "message": "Generate monthly P&L, Balance Sheet, and Cash Flow for previous month",
        "deliver_to": {"teams_channel": "finance"},
        "db": None,
        "session_id": "scheduler",
    }
    result = await agent.handle_report_generation(task)
    logger.info(f"generate_monthly_statements completed: {result.get('content', '')[:200]}")
