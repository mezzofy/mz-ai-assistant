"""
Sales Lead Automation Tasks — scheduled Celery tasks for the Sales department.

Tasks:
    sales.ingest_leads_from_email    — Daily 01:00 UTC (09:00 HKT)
        Scan hello@/sales@ inboxes; LLM-extract leads; dedup + insert.

    sales.ingest_leads_from_tickets  — Daily 01:10 UTC (09:10 HKT)
        Query support_tickets WHERE type IN contact_form/new_lead/sales_inquiry;
        LLM-enrich; dedup + insert. Skips gracefully if table missing.

    sales.research_new_leads         — Weekly Mon 01:00 UTC (09:00 HKT)
        Load targets from config; LinkedIn/web search; LLM quality-score;
        insert if score >= min_quality_score.

    sales.daily_crm_digest           — Daily 01:30 UTC (09:30 HKT)
        Query 24h lead activity; group by PIC; post to Teams #sales;
        send personalised HTML email per PIC.

All tasks:
    - Use asyncio.run() at the Celery/async boundary.
    - Use lazy inline imports for *Ops classes (per project pattern).
    - Rate-limit concurrent LLM calls via asyncio.Semaphore(5).
    - Log start/end with run_id; per-item try/except (never abort batch on single failure).
    - Store UTC in DB; convert to HKT for display.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger("mezzofy.tasks.sales")

# ── LLM Prompts ───────────────────────────────────────────────────────────────

EXTRACT_LEAD_FROM_EMAIL_PROMPT = """
You are a sales data extractor. Given the following email, extract structured lead information.

Email Subject: {subject}
Email From: {from_name} <{from_email}>
Email Body:
{body_text}

Extract and return ONLY a valid JSON object with these fields:
{{
  "company_name": "string or null",
  "contact_name": "string or null",
  "contact_email": "string — use the sender email if not found in body",
  "contact_phone": "string or null",
  "industry": "string or null — infer from context if possible",
  "location": "string or null — city/country",
  "notes": "string — 1-2 sentence summary of the inquiry"
}}

Rules:
- If company_name cannot be determined, use the sender's email domain (strip TLD).
- Never invent information not present in the email.
- Return ONLY the JSON object, no explanation, no markdown fences.
"""

EXTRACT_LEAD_FROM_TICKET_PROMPT = """
You are a sales data extractor. Given a website contact form submission, extract structured information.

Ticket Subject: {subject}
Contact Name: {contact_name}
Contact Email: {contact_email}
Message Body:
{body}

Extract and return ONLY a valid JSON object:
{{
  "company_name": "string or null",
  "industry": "string or null — infer from context",
  "location": "string or null — city/country",
  "notes": "string — 1-2 sentence summary of what they are looking for"
}}

Rules:
- If company not stated, infer from email domain.
- Never invent information.
- Return ONLY the JSON object.
"""

ASSESS_AND_STRUCTURE_LEAD_PROMPT = """
You are a Mezzofy sales analyst. Mezzofy sells loyalty program and customer engagement SaaS to F&B, Retail, and service businesses in Asia-Pacific.

Evaluate the following discovered company/contact as a potential Mezzofy lead.

Company: {company_name}
Industry: {industry}
Location: {location}
Description: {description}
Website: {website}
LinkedIn URL: {linkedin_url}
Contact Name: {contact_name}
Contact Email: {contact_email}

Return ONLY a valid JSON object:
{{
  "company_name": "string",
  "contact_name": "string or null",
  "contact_email": "string or null",
  "contact_phone": "string or null",
  "industry": "string",
  "location": "string",
  "notes": "string — why this is a good lead, 1-2 sentences",
  "quality_score": integer 1-5,
  "quality_reason": "string — one sentence explanation of score"
}}

Scoring guide:
5 = Perfect fit (F&B/Retail chain, Asia, no obvious loyalty system)
4 = Good fit (right industry, right region)
3 = Possible fit (adjacent industry or unclear region)
2 = Weak fit (wrong industry or very small)
1 = Not a fit (B2B SaaS, government, wrong geography)

Return ONLY the JSON object.
"""

# ── Default research targets ──────────────────────────────────────────────────

_DEFAULT_RESEARCH_TARGETS = [
    {
        "query": "loyalty program F&B Singapore",
        "source": "linkedin",
        "industry": "F&B",
        "location": "Singapore",
        "max_results": 15,
    },
    {
        "query": "retail loyalty program Hong Kong",
        "source": "linkedin",
        "industry": "Retail",
        "location": "Hong Kong",
        "max_results": 15,
    },
    {
        "query": "restaurant group loyalty Asia Pacific",
        "source": "web",
        "industry": "F&B",
        "location": "Asia",
        "max_results": 10,
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _hkt_window_yesterday():
    """Return (start_utc, end_utc) for yesterday in HKT (UTC+8)."""
    hkt_offset = timedelta(hours=8)
    now_hkt = datetime.now(timezone.utc) + hkt_offset
    yesterday_hkt = now_hkt.date() - timedelta(days=1)

    start_hkt = datetime(
        yesterday_hkt.year, yesterday_hkt.month, yesterday_hkt.day,
        0, 0, 0, tzinfo=timezone.utc
    ) - hkt_offset

    end_hkt = datetime(
        yesterday_hkt.year, yesterday_hkt.month, yesterday_hkt.day,
        23, 59, 59, tzinfo=timezone.utc
    ) - hkt_offset

    return start_hkt, end_hkt


def _hkt_now_str() -> str:
    """Return current HKT date as 'YYYY-MM-DD HKT' string for display."""
    import pytz
    hkt = pytz.timezone("Asia/Hong_Kong")
    return datetime.now(hkt).strftime("%Y-%m-%d HKT")


def _parse_llm_json(text: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    text = text.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.startswith("```")
        )
    return json.loads(text.strip())


async def _llm_extract(prompt: str, model: str = "claude-haiku-4-5-20251001") -> str:
    """Call LLM with a single-turn prompt; return the raw response text."""
    import anthropic
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=512,
        system="You are a precise data extraction assistant. Return only valid JSON.",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text if response.content else ""


async def _post_teams(channel: str, message: str, config: dict) -> None:
    """Post a message to a Teams channel (fire-and-forget)."""
    try:
        from app.tools.communication.teams_ops import TeamsOps
        ops = TeamsOps(config)
        await ops._send_channel_message(channel=channel, message=message)
    except Exception as e:
        logger.warning(f"_post_teams failed (non-fatal): {e}")


async def _send_email(to: str, subject: str, body_html: str, config: dict) -> None:
    """Send HTML email via Outlook (fire-and-forget)."""
    try:
        from app.tools.communication.outlook_ops import OutlookOps
        ops = OutlookOps(config)
        await ops._send_email(
            to=[to] if isinstance(to, str) else to,
            subject=subject,
            body_html=body_html,
        )
    except Exception as e:
        logger.warning(f"_send_email to {to} failed (non-fatal): {e}")


async def _audit(user_id: str, action: str, details: dict, config: dict = None) -> None:
    """Write to audit_log (fire-and-forget)."""
    try:
        from app.core.audit import log_action
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await log_action(
                db=db,
                user_id=user_id,
                action=action,
                resource="crm",
                details=details,
            )
    except Exception as e:
        logger.warning(f"_audit failed (non-fatal): {e}")


# ── Task 3.1 — Email Lead Ingestion ───────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="sales.ingest_leads_from_email",
    queue="sales",
)
def ingest_leads_from_email(self):
    """Daily email lead ingestion from hello@/sales@ mailboxes."""
    logger.info(f"[Task] sales.ingest_leads_from_email started | run_id={self.request.id}")
    try:
        result = asyncio.run(_ingest_leads_from_email_async(self.request.id))
        logger.info(
            f"[Task] sales.ingest_leads_from_email done | run_id={self.request.id} | {result}"
        )
        return result
    except Exception as exc:
        logger.error(f"sales.ingest_leads_from_email failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


async def _ingest_leads_from_email_async(run_id: str) -> dict:
    from app.core.config import get_config
    from app.tools.database.crm_ops import CRMOps
    from app.tools.communication.outlook_ops import OutlookOps

    config = get_config()
    crm = CRMOps(config)
    outlook = OutlookOps(config)

    sales_cfg = (config or {}).get("sales", {})
    ingestion_cfg = sales_cfg.get("lead_ingestion", {})
    mailboxes = ingestion_cfg.get("email_mailboxes", ["hello@mezzofy.com", "sales@mezzofy.com"])
    internal_domain = ingestion_cfg.get("internal_domain", "mezzofy.com")
    spam_patterns = ingestion_cfg.get("spam_subject_patterns", [
        r"(?i)out of office",
        r"(?i)auto.?reply",
        r"(?i)delivery (failed|failure|status)",
        r"(?i)unsubscribe",
    ])

    window_start, window_end = _hkt_window_yesterday()
    semaphore = asyncio.Semaphore(5)

    total = 0
    inserted = 0
    skipped_dup = 0
    skipped_internal = 0
    failed = 0

    for mailbox in mailboxes:
        try:
            emails_result = await outlook._read_emails(
                mailbox=mailbox,
                received_after=window_start.isoformat(),
                received_before=window_end.isoformat(),
                folder="Inbox",
                limit=100,
            )
            emails = (emails_result.get("output", {}) or {}).get("emails", []) \
                if emails_result.get("success") else []
        except Exception as e:
            logger.error(f"Failed to read mailbox {mailbox}: {e}")
            continue

        for email in emails:
            total += 1
            try:
                sender_email = email.get("from_email", email.get("sender", ""))
                sender_name = email.get("from_name", email.get("sender_name", ""))
                subject = email.get("subject", "")
                body = email.get("body", email.get("body_text", ""))
                source_ref = email.get("id", email.get("message_id", ""))

                # Skip internal
                if sender_email.lower().endswith(f"@{internal_domain}"):
                    skipped_internal += 1
                    continue

                # Skip spam/OOO
                if any(re.search(p, subject) for p in spam_patterns):
                    skipped_internal += 1
                    continue

                # Dedup check
                if source_ref and await crm.check_duplicate_lead("email", source_ref):
                    skipped_dup += 1
                    continue

                # LLM extraction
                async with semaphore:
                    prompt = EXTRACT_LEAD_FROM_EMAIL_PROMPT.format(
                        subject=subject,
                        from_name=sender_name,
                        from_email=sender_email,
                        body_text=body[:3000],
                    )
                    try:
                        raw = await _llm_extract(prompt, model="claude-haiku-4-5-20251001")
                        lead_data = _parse_llm_json(raw)
                    except Exception as e:
                        logger.error(f"LLM extraction failed for email {source_ref}: {e}")
                        failed += 1
                        continue

                lead_data["source"] = "email"
                lead_data["source_ref"] = source_ref
                lead_data["status"] = "new"

                result = await crm.create_lead_safe(lead_data)
                if result.get("success"):
                    if result["output"].get("skipped"):
                        skipped_dup += 1
                    else:
                        inserted += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Error processing email in {mailbox}: {e}")
                failed += 1

    date_str = _hkt_now_str()
    summary = (
        f"📧 Email Lead Ingestion — {date_str}\n"
        f"Mailboxes scanned: {', '.join(mailboxes)}\n"
        f"Emails processed: {total}\n"
        f"New leads inserted: {inserted}\n"
        f"Duplicates skipped: {skipped_dup}\n"
        f"Internal/spam skipped: {skipped_internal}\n"
        f"Failed: {failed}"
    )

    digest_cfg = sales_cfg.get("digest", {})
    teams_channel = digest_cfg.get("teams_channel", "sales")
    await _post_teams(teams_channel, summary, config)

    counts = {
        "total": total, "inserted": inserted,
        "skipped_duplicate": skipped_dup,
        "skipped_internal": skipped_internal,
        "failed": failed,
    }
    await _audit("system", "email_lead_ingestion", {**counts, "run_id": run_id}, config)
    return counts


# ── Task 3.2 — Ticket Lead Ingestion ─────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="sales.ingest_leads_from_tickets",
    queue="sales",
)
def ingest_leads_from_tickets(self):
    """Daily ticket lead ingestion from support_tickets table."""
    logger.info(f"[Task] sales.ingest_leads_from_tickets started | run_id={self.request.id}")
    try:
        result = asyncio.run(_ingest_leads_from_tickets_async(self.request.id))
        logger.info(
            f"[Task] sales.ingest_leads_from_tickets done | run_id={self.request.id} | {result}"
        )
        return result
    except Exception as exc:
        logger.error(f"sales.ingest_leads_from_tickets failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


async def _ingest_leads_from_tickets_async(run_id: str) -> dict:
    from app.core.config import get_config
    from app.core.database import AsyncSessionLocal
    from app.tools.database.crm_ops import CRMOps
    from sqlalchemy import text

    config = get_config()
    crm = CRMOps(config)

    sales_cfg = (config or {}).get("sales", {})
    ingestion_cfg = sales_cfg.get("lead_ingestion", {})
    ticket_lead_types = ingestion_cfg.get(
        "ticket_lead_types", ["contact_form", "new_lead", "sales_inquiry"]
    )

    # Runtime check: does support_tickets exist?
    try:
        async with AsyncSessionLocal() as db:
            row = await db.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables "
                    "  WHERE table_name = 'support_tickets'"
                    ")"
                )
            )
            has_table = row.scalar()
    except Exception as e:
        logger.error(f"Cannot check support_tickets existence: {e}")
        has_table = False

    if not has_table:
        logger.warning(
            "[Task] sales.ingest_leads_from_tickets: support_tickets table not found — skipping"
        )
        return {"skipped": True, "reason": "support_tickets table not found"}

    window_start, window_end = _hkt_window_yesterday()
    semaphore = asyncio.Semaphore(5)

    total = 0
    inserted = 0
    skipped_dup = 0
    failed = 0

    try:
        async with AsyncSessionLocal() as db:
            types_placeholder = ", ".join(f"'{t}'" for t in ticket_lead_types)
            sql = text(f"""
                SELECT id, type, subject, body, contact_name, contact_email,
                       contact_phone, company, source_channel, created_at
                FROM support_tickets
                WHERE type IN ({types_placeholder})
                  AND created_at BETWEEN :window_start AND :window_end
            """)
            result = await db.execute(
                sql, {"window_start": window_start, "window_end": window_end}
            )
            tickets = [dict(r) for r in result.mappings().all()]
    except Exception as e:
        logger.error(f"Failed to query support_tickets: {e}")
        return {"error": str(e)}

    for ticket in tickets:
        total += 1
        try:
            ticket_id = str(ticket["id"])
            source_ref = f"ticket:{ticket_id}"

            if await crm.check_duplicate_lead("ticket", source_ref):
                skipped_dup += 1
                continue

            body = ticket.get("body") or ""
            if len(body) > 50:
                async with semaphore:
                    prompt = EXTRACT_LEAD_FROM_TICKET_PROMPT.format(
                        subject=ticket.get("subject", ""),
                        contact_name=ticket.get("contact_name", ""),
                        contact_email=ticket.get("contact_email", ""),
                        body=body[:3000],
                    )
                    try:
                        raw = await _llm_extract(prompt, model="claude-haiku-4-5-20251001")
                        enrichment = _parse_llm_json(raw)
                    except Exception as e:
                        logger.error(f"LLM enrichment failed for ticket {ticket_id}: {e}")
                        enrichment = {}
            else:
                enrichment = {}

            source_channel = ticket.get("source_channel") or "website"
            lead_data = {
                "company_name": (
                    ticket.get("company")
                    or enrichment.get("company_name")
                    or ""
                ),
                "contact_name": ticket.get("contact_name") or "",
                "contact_email": ticket.get("contact_email") or "",
                "contact_phone": ticket.get("contact_phone"),
                "industry": enrichment.get("industry"),
                "location": enrichment.get("location"),
                "source": "ticket",
                "source_ref": source_ref,
                "notes": (
                    enrichment.get("notes")
                    or f"Via {source_channel} contact form. Subject: {ticket.get('subject', '')}"
                ),
                "status": "new",
            }

            result = await crm.create_lead_safe(lead_data)
            if result.get("success"):
                if result["output"].get("skipped"):
                    skipped_dup += 1
                else:
                    inserted += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Error processing ticket {ticket.get('id')}: {e}")
            failed += 1

    date_str = _hkt_now_str()
    summary = (
        f"📋 Ticket Lead Ingestion — {date_str}\n"
        f"Tickets scanned: {total}\n"
        f"New leads inserted: {inserted}\n"
        f"Duplicates skipped: {skipped_dup}\n"
        f"Failed: {failed}"
    )

    digest_cfg = sales_cfg.get("digest", {})
    teams_channel = digest_cfg.get("teams_channel", "sales")
    await _post_teams(teams_channel, summary, config)

    counts = {
        "total": total, "inserted": inserted,
        "skipped_duplicate": skipped_dup,
        "failed": failed,
    }
    await _audit("system", "ticket_lead_ingestion", {**counts, "run_id": run_id}, config)
    return counts


# ── Task 3.3 — Web / LinkedIn Lead Research ───────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="sales.research_new_leads",
    queue="sales",
)
def research_new_leads(self, targets: list = None):
    """Weekly web/LinkedIn lead research. Also triggered manually via API."""
    logger.info(f"[Task] sales.research_new_leads started | run_id={self.request.id}")
    try:
        result = asyncio.run(_research_new_leads_async(self.request.id, targets))
        logger.info(
            f"[Task] sales.research_new_leads done | run_id={self.request.id} | {result}"
        )
        return result
    except Exception as exc:
        logger.error(f"sales.research_new_leads failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


async def _research_new_leads_async(run_id: str, override_targets: list = None) -> dict:
    from app.core.config import get_config
    from app.tools.database.crm_ops import CRMOps

    config = get_config()
    crm = CRMOps(config)

    sales_cfg = (config or {}).get("sales", {})
    research_cfg = sales_cfg.get("lead_research", {})

    if not research_cfg.get("enabled", True):
        logger.info("sales.research_new_leads: disabled in config — skipping")
        return {"skipped": True, "reason": "disabled in config"}

    targets = override_targets or research_cfg.get("targets") or _DEFAULT_RESEARCH_TARGETS
    min_quality = research_cfg.get("min_quality_score", 3)

    semaphore = asyncio.Semaphore(5)
    total_discovered = 0
    inserted = 0
    low_quality = 0
    duplicates = 0
    failed = 0

    for target in targets:
        query = target.get("query", "")
        source_type = target.get("source", "web")
        industry = target.get("industry", "")
        location = target.get("location", "")
        max_results = target.get("max_results", 15)

        discovered = []

        if "linkedin" in source_type:
            try:
                from app.tools.web.linkedin_ops import LinkedInOps
                li = LinkedInOps(config)
                results = await li._search(query=query, max_results=max_results)
                if isinstance(results, list):
                    discovered.extend(results)
                elif isinstance(results, dict) and results.get("results"):
                    discovered.extend(results["results"])
            except Exception as e:
                logger.warning(f"LinkedIn search failed for '{query}': {e}")

        if "web" in source_type:
            try:
                from app.tools.web.browser_ops import BrowserOps
                browser = BrowserOps(config)
                results = await browser._search(query=query, max_results=max_results)
                if isinstance(results, list):
                    discovered.extend(results)
            except Exception as e:
                logger.warning(f"Web search failed for '{query}': {e}")

        total_discovered += len(discovered)

        # Dedup within batch + score with LLM
        seen_refs = set()
        for item in discovered:
            try:
                source_ref = (
                    item.get("linkedin_url")
                    or item.get("website")
                    or item.get("domain")
                    or re.sub(r"[^a-z0-9]", "-", (item.get("company_name") or "").lower())
                )
                if not source_ref or source_ref in seen_refs:
                    continue
                seen_refs.add(source_ref)

                lead_source = "linkedin" if "linkedin" in (source_ref or "") else "web"

                if await crm.check_duplicate_lead(lead_source, source_ref):
                    duplicates += 1
                    continue

                async with semaphore:
                    prompt = ASSESS_AND_STRUCTURE_LEAD_PROMPT.format(
                        company_name=item.get("company_name", ""),
                        industry=item.get("industry") or industry,
                        location=item.get("location") or location,
                        description=item.get("description", ""),
                        website=item.get("website", ""),
                        linkedin_url=item.get("linkedin_url", ""),
                        contact_name=item.get("contact_name", ""),
                        contact_email=item.get("contact_email", ""),
                    )
                    try:
                        raw = await _llm_extract(prompt, model="claude-sonnet-4-6")
                        assessment = _parse_llm_json(raw)
                    except Exception as e:
                        logger.error(f"LLM assessment failed for {source_ref}: {e}")
                        failed += 1
                        continue

                quality_score = assessment.get("quality_score", 0)
                if quality_score < min_quality:
                    logger.debug(
                        f"research: low quality ({quality_score}) skipped: {source_ref}"
                    )
                    low_quality += 1
                    continue

                lead_data = {
                    **assessment,
                    "source": lead_source,
                    "source_ref": source_ref,
                    "status": "new",
                }

                result = await crm.create_lead_safe(lead_data)
                if result.get("success"):
                    if result["output"].get("skipped"):
                        duplicates += 1
                    else:
                        inserted += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Error processing research item: {e}")
                failed += 1

    date_str = _hkt_now_str()
    summary = (
        f"🔍 Lead Research — {date_str}\n"
        f"Targets researched: {len(targets)}\n"
        f"Profiles discovered: {total_discovered}\n"
        f"New leads inserted: {inserted}\n"
        f"Low quality skipped: {low_quality}\n"
        f"Duplicates skipped: {duplicates}\n"
        f"Failed: {failed}"
    )

    digest_cfg = sales_cfg.get("digest", {})
    teams_channel = digest_cfg.get("teams_channel", "sales")
    await _post_teams(teams_channel, summary, config)

    counts = {
        "targets": len(targets),
        "total_discovered": total_discovered,
        "inserted": inserted,
        "low_quality": low_quality,
        "duplicates": duplicates,
        "failed": failed,
    }
    await _audit("system", "lead_research", {**counts, "run_id": run_id}, config)
    return counts


# ── Task 3.4 — Daily CRM Digest ───────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    name="sales.daily_crm_digest",
    queue="sales",
)
def daily_crm_digest(self):
    """Daily CRM status digest — post to Teams + email each PIC."""
    logger.info(f"[Task] sales.daily_crm_digest started | run_id={self.request.id}")
    try:
        result = asyncio.run(_daily_crm_digest_async(self.request.id))
        logger.info(
            f"[Task] sales.daily_crm_digest done | run_id={self.request.id} | {result}"
        )
        return result
    except Exception as exc:
        logger.error(f"sales.daily_crm_digest failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


async def _daily_crm_digest_async(run_id: str, preview_only: bool = False) -> dict:
    """
    Core digest logic. preview_only=True skips Teams/email sends (used by the
    GET /sales/leads/digest/preview API endpoint).
    """
    from app.core.config import get_config
    from app.core.database import AsyncSessionLocal
    from app.tools.communication.push_ops import send_push
    from sqlalchemy import text

    config = get_config()
    sales_cfg = (config or {}).get("sales", {})
    digest_cfg = sales_cfg.get("digest", {})
    teams_channel = digest_cfg.get("teams_channel", "sales")
    send_pic_emails = digest_cfg.get("send_pic_emails", True)
    send_push_notifs = digest_cfg.get("send_push_notifications", True)

    # Query leads active in last 24h
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT sl.id, sl.company_name, sl.contact_name, sl.contact_email,
                       sl.industry, sl.source, sl.status, sl.assigned_to,
                       sl.notes, sl.created_at, sl.last_status_update,
                       sl.follow_up_date, sl.last_contacted, sl.source_ref,
                       u.name AS pic_name, u.email AS pic_email
                FROM sales_leads sl
                LEFT JOIN users u ON sl.assigned_to = u.id
                WHERE sl.created_at >= NOW() - INTERVAL '24 hours'
                   OR sl.last_status_update >= NOW() - INTERVAL '24 hours'
                ORDER BY sl.created_at DESC
            """)
        )
        leads = [dict(r) for r in result.mappings().all()]

    # Serialize datetime fields
    for lead in leads:
        for k, v in lead.items():
            if hasattr(v, "isoformat"):
                lead[k] = v.isoformat()

    # Build source and status breakdowns
    source_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for lead in leads:
        source_counts[lead["source"]] = source_counts.get(lead["source"], 0) + 1
        status_counts[lead["status"]] = status_counts.get(lead["status"], 0) + 1

    unassigned = [l for l in leads if not l.get("assigned_to")]
    top_unassigned = unassigned[:5]

    import pytz
    hkt = pytz.timezone("Asia/Hong_Kong")
    today_hkt = datetime.now(hkt).strftime("%Y-%m-%d")
    follow_up_today = [l for l in leads if (l.get("follow_up_date") or "").startswith(today_hkt)]

    date_str = _hkt_now_str()

    # Overall Teams digest
    source_lines = "\n".join(f"  • {s}: {c}" for s, c in sorted(source_counts.items()))
    status_lines = "\n".join(f"  • {s}: {c}" for s, c in sorted(status_counts.items()))
    unassigned_lines = "\n".join(
        f"  • {l['company_name']} ({l['source']}) — {(l.get('notes') or '')[:60]}"
        for l in top_unassigned
    )

    teams_msg = (
        f"📊 Daily CRM Digest — {date_str}\n"
        f"Total active leads (24h): {len(leads)}\n\n"
        f"By source:\n{source_lines or '  (none)'}\n\n"
        f"By status:\n{status_lines or '  (none)'}\n\n"
        f"Top unassigned leads:\n{unassigned_lines or '  (none)'}\n\n"
        f"Follow-up due today: {len(follow_up_today)}"
    )

    if not preview_only:
        await _post_teams(teams_channel, teams_msg, config)

    # Group by PIC
    by_pic: dict[str, list] = {}
    for lead in leads:
        pic_id = lead.get("assigned_to") or "unassigned"
        by_pic.setdefault(pic_id, []).append(lead)

    emails_sent = 0
    if not preview_only and send_pic_emails:
        for pic_id, pic_leads in by_pic.items():
            if pic_id == "unassigned":
                continue
            pic_email = pic_leads[0].get("pic_email")
            pic_name = pic_leads[0].get("pic_name") or pic_id
            if not pic_email:
                continue

            rows_html = ""
            for lead in pic_leads:
                rows_html += (
                    f"<tr>"
                    f"<td>{lead['company_name']}</td>"
                    f"<td>{lead['status']}</td>"
                    f"<td>{lead.get('last_contacted') or '—'}</td>"
                    f"<td>{lead.get('follow_up_date') or '—'}</td>"
                    f"<td>{(lead.get('notes') or '')[:80]}</td>"
                    f"</tr>"
                )

            body_html = f"""
<html><body>
<h2>Your CRM Leads — {date_str}</h2>
<p>Hi {pic_name}, here is your daily lead summary:</p>
<table border="1" cellpadding="5" style="border-collapse:collapse;font-family:sans-serif;">
  <thead>
    <tr>
      <th>Company</th><th>Status</th><th>Last Contacted</th>
      <th>Follow Up</th><th>Notes</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
<p>Total: {len(pic_leads)} lead(s) needing attention.</p>
</body></html>
"""
            await _send_email(
                to=pic_email,
                subject=f"[Mezzofy CRM] Your leads for {date_str}",
                body_html=body_html,
                config=config,
            )
            emails_sent += 1

    counts = {
        "total_leads": len(leads),
        "by_source": source_counts,
        "by_status": status_counts,
        "unassigned": len(unassigned),
        "follow_up_today": len(follow_up_today),
        "emails_sent": emails_sent,
        "leads": leads if preview_only else [],
    }

    if not preview_only:
        await _audit("system", "daily_crm_digest", {
            "total_leads": len(leads),
            "emails_sent": emails_sent,
            "run_id": run_id,
        }, config)

    return counts
