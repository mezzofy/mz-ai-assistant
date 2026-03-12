"""
Tests for Sales Lead Automation — Celery tasks + API endpoints.

Coverage:
  1. test_email_lead_ingestion_inserts_new_lead
  2. test_email_lead_ingestion_skips_duplicate
  3. test_email_lead_ingestion_skips_internal
  4. test_ticket_lead_ingestion_inserts_new_lead
  5. test_patch_lead_status_valid_transition
  6. test_patch_lead_status_invalid_transition
  7. test_dedup_index_prevents_duplicate
  8. test_manual_research_trigger

All external calls (LLM, Outlook, Teams, Celery) are mocked.
*Ops classes patched at SOURCE module per project pattern.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Ensure test env is loaded before app imports ─────────────────────────────
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.conftest import auth_headers, USERS, TEST_CONFIG


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fake_email(
    sender_email="john@acme.com",
    sender_name="John Smith",
    subject="Inquiry about loyalty program",
    body="We are a F&B chain looking for a loyalty solution.",
    msg_id=None,
) -> dict:
    return {
        "id": msg_id or str(uuid.uuid4()),
        "from_email": sender_email,
        "from_name": sender_name,
        "subject": subject,
        "body": body,
    }


_GOOD_LLM_LEAD_JSON = json.dumps({
    "company_name": "Acme Corp",
    "contact_name": "John Smith",
    "contact_email": "john@acme.com",
    "contact_phone": None,
    "industry": "F&B",
    "location": "Singapore",
    "notes": "F&B chain interested in loyalty platform.",
})

_GOOD_LLM_TICKET_JSON = json.dumps({
    "company_name": "Beta Retail",
    "industry": "Retail",
    "location": "Hong Kong",
    "notes": "Retail chain inquiring about loyalty solution.",
})


# ── Test 1: Email ingestion inserts new lead ─────────────────────────────────

@pytest.mark.asyncio
async def test_email_lead_ingestion_inserts_new_lead():
    """
    One new email from external sender → LLM extracts lead → create_lead_safe called once.
    """
    email = _fake_email()
    msg_id = email["id"]

    crm_create_safe_mock = AsyncMock(return_value={
        "success": True,
        "output": {"skipped": False, "lead_id": str(uuid.uuid4())},
    })
    crm_check_dup_mock = AsyncMock(return_value=False)

    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.tools.database.crm_ops.CRMOps.check_duplicate_lead", crm_check_dup_mock), \
         patch("app.tools.database.crm_ops.CRMOps.create_lead_safe", crm_create_safe_mock), \
         patch("app.tools.communication.outlook_ops.OutlookOps._read_emails",
               AsyncMock(return_value={"success": True, "output": {"emails": [email], "count": 1}})), \
         patch("app.tasks.sales_lead_tasks._llm_extract",
               AsyncMock(return_value=_GOOD_LLM_LEAD_JSON)), \
         patch("app.tasks.sales_lead_tasks._post_teams", AsyncMock()), \
         patch("app.tasks.sales_lead_tasks._audit", AsyncMock()):

        from app.tasks.sales_lead_tasks import _ingest_leads_from_email_async
        result = await _ingest_leads_from_email_async(run_id="test-run-1")

    assert result["inserted"] == 1
    assert result["skipped_duplicate"] == 0
    assert result["skipped_internal"] == 0
    crm_create_safe_mock.assert_awaited_once()

    # Verify the lead_data passed to create_lead_safe
    call_args = crm_create_safe_mock.call_args[0][0]
    assert call_args["source"] == "email"
    assert call_args["source_ref"] == msg_id
    assert call_args["status"] == "new"


# ── Test 2: Email ingestion skips duplicate ───────────────────────────────────

@pytest.mark.asyncio
async def test_email_lead_ingestion_skips_duplicate():
    """
    Email already present in DB → check_duplicate_lead returns True → no insertion.
    """
    email = _fake_email()

    crm_create_safe_mock = AsyncMock()
    crm_check_dup_mock = AsyncMock(return_value=True)  # already exists

    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.tools.database.crm_ops.CRMOps.check_duplicate_lead", crm_check_dup_mock), \
         patch("app.tools.database.crm_ops.CRMOps.create_lead_safe", crm_create_safe_mock), \
         patch("app.tools.communication.outlook_ops.OutlookOps._read_emails",
               AsyncMock(return_value={"success": True, "output": {"emails": [email], "count": 1}})), \
         patch("app.tasks.sales_lead_tasks._llm_extract", AsyncMock()), \
         patch("app.tasks.sales_lead_tasks._post_teams", AsyncMock()), \
         patch("app.tasks.sales_lead_tasks._audit", AsyncMock()):

        from app.tasks.sales_lead_tasks import _ingest_leads_from_email_async
        result = await _ingest_leads_from_email_async(run_id="test-run-2")

    assert result["inserted"] == 0
    assert result["skipped_duplicate"] == 1
    # LLM and create_lead_safe should NOT have been called
    crm_create_safe_mock.assert_not_awaited()


# ── Test 3: Email ingestion skips internal sender ────────────────────────────

@pytest.mark.asyncio
async def test_email_lead_ingestion_skips_internal():
    """
    Email from @mezzofy.com → skipped before LLM is called.
    """
    email = _fake_email(sender_email="alice@mezzofy.com")

    llm_mock = AsyncMock()
    crm_create_safe_mock = AsyncMock()

    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.tools.database.crm_ops.CRMOps.check_duplicate_lead", AsyncMock(return_value=False)), \
         patch("app.tools.database.crm_ops.CRMOps.create_lead_safe", crm_create_safe_mock), \
         patch("app.tools.communication.outlook_ops.OutlookOps._read_emails",
               AsyncMock(return_value={"success": True, "output": {"emails": [email], "count": 1}})), \
         patch("app.tasks.sales_lead_tasks._llm_extract", llm_mock), \
         patch("app.tasks.sales_lead_tasks._post_teams", AsyncMock()), \
         patch("app.tasks.sales_lead_tasks._audit", AsyncMock()):

        from app.tasks.sales_lead_tasks import _ingest_leads_from_email_async
        result = await _ingest_leads_from_email_async(run_id="test-run-3")

    assert result["skipped_internal"] == 1
    assert result["inserted"] == 0
    llm_mock.assert_not_awaited()
    crm_create_safe_mock.assert_not_awaited()


# ── Test 4: Ticket ingestion inserts new lead ─────────────────────────────────

@pytest.mark.asyncio
async def test_ticket_lead_ingestion_inserts_new_lead():
    """
    support_tickets table exists, one qualifying ticket → lead inserted.
    """
    import uuid as _uuid
    ticket = {
        "id": _uuid.uuid4(),
        "type": "contact_form",
        "subject": "Interested in loyalty platform",
        "body": "We are a retail company looking for a loyalty solution for 50+ stores.",
        "contact_name": "Jane Doe",
        "contact_email": "jane@betaretail.com",
        "contact_phone": "+852 1234 5678",
        "company": "Beta Retail",
        "source_channel": "website",
        "created_at": "2026-03-11T12:00:00",
    }

    crm_create_safe_mock = AsyncMock(return_value={
        "success": True,
        "output": {"skipped": False, "lead_id": str(_uuid.uuid4())},
    })

    # Mock DB result for support_tickets query
    mock_exists_result = MagicMock()
    mock_exists_result.scalar.return_value = True

    mock_tickets_result = MagicMock()
    mock_tickets_result.mappings.return_value.all.return_value = [ticket]

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock(side_effect=[mock_exists_result, mock_tickets_result])

    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.tools.database.crm_ops.CRMOps.check_duplicate_lead",
               AsyncMock(return_value=False)), \
         patch("app.tools.database.crm_ops.CRMOps.create_lead_safe", crm_create_safe_mock), \
         patch("app.core.database.AsyncSessionLocal", return_value=mock_db), \
         patch("app.tasks.sales_lead_tasks._llm_extract",
               AsyncMock(return_value=_GOOD_LLM_TICKET_JSON)), \
         patch("app.tasks.sales_lead_tasks._post_teams", AsyncMock()), \
         patch("app.tasks.sales_lead_tasks._audit", AsyncMock()):

        from app.tasks.sales_lead_tasks import _ingest_leads_from_tickets_async
        result = await _ingest_leads_from_tickets_async(run_id="test-run-4")

    assert result.get("inserted") == 1
    assert result.get("skipped_duplicate") == 0
    crm_create_safe_mock.assert_awaited_once()

    call_args = crm_create_safe_mock.call_args[0][0]
    assert call_args["source"] == "ticket"
    assert call_args["source_ref"] == f"ticket:{ticket['id']}"


# ── Test 5: API — valid status transition ─────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_lead_status_valid_transition(client):
    """
    PATCH /sales/leads/{id}/status with new → contacted → 200, notes appended.
    """
    lead_id = str(uuid.uuid4())
    user_id = USERS["sales_manager"]["user_id"]

    mock_crm_result = {
        "success": True,
        "output": {
            "lead": {
                "id": lead_id,
                "status": "contacted",
                "notes": "[2026-03-12 01:00 UTC] Status → contacted: Called John",
                "last_status_update": "2026-03-12T01:00:00+00:00",
            },
            "previous_status": "new",
        },
    }

    # Mock DB check for lead existence
    mock_row = {"id": lead_id, "assigned_to": user_id}
    mock_db_result = MagicMock()
    mock_db_result.mappings.return_value.one_or_none.return_value = mock_row

    mock_db_session = AsyncMock()
    mock_db_session.execute = AsyncMock(return_value=mock_db_result)
    mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_db_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.tools.database.crm_ops.CRMOps.update_lead_status",
               AsyncMock(return_value=mock_crm_result)), \
         patch("app.core.database.get_db", return_value=mock_db_session):

        response = await client.patch(
            f"/sales/leads/{lead_id}/status",
            json={"new_status": "contacted", "remarks": "Called John"},
            headers=auth_headers("sales_manager"),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["lead"]["status"] == "contacted"
    assert "contacted" in data["lead"]["notes"]


# ── Test 6: API — invalid status transition ───────────────────────────────────

@pytest.mark.asyncio
async def test_patch_lead_status_invalid_transition(client):
    """
    PATCH with new → closed_won (invalid jump) → 400 with error message.
    """
    lead_id = str(uuid.uuid4())
    user_id = USERS["sales_manager"]["user_id"]

    mock_crm_result = {
        "success": False,
        "error": "Invalid status transition: new → closed_won. Allowed: contacted, disqualified",
    }

    mock_row = {"id": lead_id, "assigned_to": user_id}
    mock_db_result = MagicMock()
    mock_db_result.mappings.return_value.one_or_none.return_value = mock_row

    mock_db_session = AsyncMock()
    mock_db_session.execute = AsyncMock(return_value=mock_db_result)
    mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_db_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.tools.database.crm_ops.CRMOps.update_lead_status",
               AsyncMock(return_value=mock_crm_result)), \
         patch("app.core.database.get_db", return_value=mock_db_session):

        response = await client.patch(
            f"/sales/leads/{lead_id}/status",
            json={"new_status": "closed_won"},
            headers=auth_headers("sales_manager"),
        )

    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["detail"]


# ── Test 7: Dedup index prevents duplicate ────────────────────────────────────

@pytest.mark.asyncio
async def test_dedup_index_prevents_duplicate():
    """
    create_lead_safe called twice with same (source, source_ref) →
    second call returns skipped=True (dedup caught by check_duplicate_lead).
    """
    from app.core.config import get_config

    source = "email"
    source_ref = "msg_dedup_001"
    lead_data = {
        "company_name": "Dedup Corp",
        "contact_email": "test@dedupcorp.com",
        "contact_name": "Test User",
        "industry": "F&B",
        "source": source,
        "source_ref": source_ref,
        "status": "new",
    }

    # Simulate: first call → not duplicate; second call → duplicate
    check_calls = [False, True]
    check_iter = iter(check_calls)
    check_mock = AsyncMock(side_effect=lambda *a, **kw: next(check_iter))

    insert_mock = AsyncMock(return_value={
        "success": True,
        "output": {"lead_id": str(uuid.uuid4())},
    })

    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.tools.database.crm_ops.CRMOps.check_duplicate_lead", check_mock), \
         patch("app.tools.database.crm_ops.CRMOps._create_lead", insert_mock):

        from app.tools.database.crm_ops import CRMOps
        crm = CRMOps(TEST_CONFIG)

        result1 = await crm.create_lead_safe(lead_data)
        result2 = await crm.create_lead_safe(lead_data)

    assert result1["success"] is True
    assert result1["output"].get("skipped") is False  # first insert goes through

    assert result2["success"] is True
    assert result2["output"].get("skipped") is True
    assert result2["output"]["reason"] == "duplicate"

    # _create_lead only called once (second blocked by dedup)
    insert_mock.assert_awaited_once()


# ── Test 8: Manual research trigger ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_manual_research_trigger(client):
    """
    POST /sales/leads/research → 202 + task_id returned + Celery task enqueued.
    """
    mock_task = MagicMock()
    mock_task.id = "celery-task-uuid-1234"

    with patch(
        "app.tasks.sales_lead_tasks.research_new_leads.apply_async",
        return_value=mock_task,
    ) as mock_apply:
        response = await client.post(
            "/sales/leads/research",
            json={},
            headers=auth_headers("sales_manager"),
        )

    assert response.status_code == 202
    data = response.json()
    assert data["task_id"] == "celery-task-uuid-1234"
    assert data["status"] == "queued"
    mock_apply.assert_called_once()
