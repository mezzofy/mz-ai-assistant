"""
Personal MS Graph Tools — delegated OAuth access to user's own Microsoft account.

Provides 18 tools across 4 categories:
  Email    (4): personal_read_emails, personal_search_emails, personal_send_email,
                personal_get_email_detail
  Calendar (5): personal_get_events, personal_create_event, personal_update_event,
                personal_delete_event, personal_find_free_slots
  Notes    (4): personal_get_notebooks, personal_get_notes, personal_search_notes,
                personal_create_note
  Teams    (5): personal_get_chats, personal_get_chat_messages, personal_send_chat_message,
                personal_get_teams, personal_get_channel_messages

Auth: per-user delegated OAuth via ms_token_service.get_valid_token(user_id)
HTTP: httpx.AsyncClient (direct Graph calls, not msgraph SDK)
Graph base: https://graph.microsoft.com/v1.0/me/

When the user has no connected MS account, all tools return a friendly prompt to connect
in Settings instead of an error.
"""

import json
import logging

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.personal_ms")

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_NOT_CONNECTED_MSG = (
    "To access your personal email, calendar, notes, or Teams, please connect your "
    "Microsoft account in Settings → Connected Accounts."
)


class PersonalMSOps(BaseTool):

    # ── Auth helper ──────────────────────────────────────────────────────────

    async def _get_headers(self, user_id: str) -> dict:
        """Return Authorization headers using the user's delegated token."""
        from app.services.ms_token_service import get_valid_token, MSNotConnectedException
        token = await get_valid_token(user_id)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _audit(self, user_id: str, action: str, resource: str, details: dict) -> None:
        """Write an entry to audit_log."""
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("""
                        INSERT INTO audit_log
                            (user_id, action, resource, details, success)
                        VALUES (:uid, :action, :resource, :details, true)
                    """),
                    {
                        "uid": user_id,
                        "action": action,
                        "resource": resource,
                        "details": json.dumps(details),
                    },
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Audit log write failed for {action}: {e}")

    def _not_connected(self) -> dict:
        return {"success": False, "error": _NOT_CONNECTED_MSG}

    # ── Tool registry ────────────────────────────────────────────────────────

    def get_tools(self) -> list[dict]:
        return [
            # ── Email tools ────────────────────────────────────────────────
            {
                "name": "personal_read_emails",
                "description": (
                    "Read emails from the user's personal Microsoft mailbox. "
                    "Accesses the user's own Outlook/Hotmail/Microsoft 365 account via delegated OAuth. "
                    "Requires the user to have connected their Microsoft account in Settings."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "folder": {
                            "type": "string",
                            "description": "Mail folder name (inbox, sentitems, drafts, deleteditems). Default: inbox",
                            "default": "inbox",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of emails to return (1-50). Default: 10",
                            "default": 10,
                        },
                        "filter": {
                            "type": "string",
                            "description": "OData filter expression (e.g. 'isRead eq false'). Optional.",
                        },
                    },
                    "required": ["user_id"],
                },
                "handler": self._read_emails,
            },
            {
                "name": "personal_search_emails",
                "description": (
                    "Search the user's personal Microsoft mailbox by keyword. "
                    "Searches across subject, body, and sender fields."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "query": {"type": "string", "description": "Search keyword or phrase"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (1-50). Default: 10",
                            "default": 10,
                        },
                    },
                    "required": ["user_id", "query"],
                },
                "handler": self._search_emails,
            },
            {
                "name": "personal_send_email",
                "description": (
                    "Send an email from the user's personal Microsoft account. "
                    "The email is sent as the connected user, not the system service account."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of recipient email addresses",
                        },
                        "subject": {"type": "string", "description": "Email subject line"},
                        "body": {"type": "string", "description": "Email body (plain text or HTML)"},
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "CC recipients. Optional.",
                        },
                        "is_html": {
                            "type": "boolean",
                            "description": "True if body is HTML, False for plain text. Default: false",
                            "default": False,
                        },
                    },
                    "required": ["user_id", "to", "subject", "body"],
                },
                "handler": self._send_email,
            },
            {
                "name": "personal_get_email_detail",
                "description": "Get full details of a specific email by its Graph message ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "message_id": {"type": "string", "description": "Graph API message ID"},
                    },
                    "required": ["user_id", "message_id"],
                },
                "handler": self._get_email_detail,
            },
            # ── Calendar tools ─────────────────────────────────────────────
            {
                "name": "personal_get_events",
                "description": (
                    "Get calendar events from the user's personal Microsoft calendar "
                    "for a given date range."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "start": {
                            "type": "string",
                            "description": "Start datetime in ISO 8601 format (e.g. 2025-03-01T00:00:00Z)",
                        },
                        "end": {
                            "type": "string",
                            "description": "End datetime in ISO 8601 format (e.g. 2025-03-07T23:59:59Z)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max events to return. Default: 20",
                            "default": 20,
                        },
                    },
                    "required": ["user_id", "start", "end"],
                },
                "handler": self._get_events,
            },
            {
                "name": "personal_create_event",
                "description": "Create a new event in the user's personal Microsoft calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "subject": {"type": "string", "description": "Event title"},
                        "start": {
                            "type": "string",
                            "description": "Start datetime ISO 8601 with timezone (e.g. 2025-03-10T09:00:00+08:00)",
                        },
                        "end": {
                            "type": "string",
                            "description": "End datetime ISO 8601 with timezone",
                        },
                        "body": {
                            "type": "string",
                            "description": "Event description/body. Optional.",
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of attendee email addresses. Optional.",
                        },
                        "location": {
                            "type": "string",
                            "description": "Event location or meeting link. Optional.",
                        },
                        "is_online": {
                            "type": "boolean",
                            "description": "Create as Teams online meeting. Default: false",
                            "default": False,
                        },
                    },
                    "required": ["user_id", "subject", "start", "end"],
                },
                "handler": self._create_event,
            },
            {
                "name": "personal_update_event",
                "description": "Update an existing event in the user's personal Microsoft calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "event_id": {"type": "string", "description": "Graph API event ID"},
                        "subject": {"type": "string", "description": "New event title. Optional."},
                        "start": {"type": "string", "description": "New start datetime ISO 8601. Optional."},
                        "end": {"type": "string", "description": "New end datetime ISO 8601. Optional."},
                        "body": {"type": "string", "description": "New description. Optional."},
                        "location": {"type": "string", "description": "New location. Optional."},
                    },
                    "required": ["user_id", "event_id"],
                },
                "handler": self._update_event,
            },
            {
                "name": "personal_delete_event",
                "description": "Delete an event from the user's personal Microsoft calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "event_id": {"type": "string", "description": "Graph API event ID"},
                    },
                    "required": ["user_id", "event_id"],
                },
                "handler": self._delete_event,
            },
            {
                "name": "personal_find_free_slots",
                "description": (
                    "Find available (free) time slots in the user's personal calendar. "
                    "Returns gaps between existing events in the given date range."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "start": {
                            "type": "string",
                            "description": "Search range start in ISO 8601 format",
                        },
                        "end": {
                            "type": "string",
                            "description": "Search range end in ISO 8601 format",
                        },
                        "min_duration_minutes": {
                            "type": "integer",
                            "description": "Minimum slot duration in minutes. Default: 30",
                            "default": 30,
                        },
                    },
                    "required": ["user_id", "start", "end"],
                },
                "handler": self._find_free_slots,
            },
            # ── Notes tools ────────────────────────────────────────────────
            {
                "name": "personal_get_notebooks",
                "description": "List the user's OneNote notebooks from their personal Microsoft account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                    },
                    "required": ["user_id"],
                },
                "handler": self._get_notebooks,
            },
            {
                "name": "personal_get_notes",
                "description": "List OneNote pages from the user's personal Microsoft account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max pages to return. Default: 20",
                            "default": 20,
                        },
                    },
                    "required": ["user_id"],
                },
                "handler": self._get_notes,
            },
            {
                "name": "personal_search_notes",
                "description": "Search OneNote pages in the user's personal Microsoft account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "query": {"type": "string", "description": "Search keyword or phrase"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results. Default: 10",
                            "default": 10,
                        },
                    },
                    "required": ["user_id", "query"],
                },
                "handler": self._search_notes,
            },
            {
                "name": "personal_create_note",
                "description": (
                    "Create a new OneNote page in the user's personal Microsoft account. "
                    "Requires a valid section ID from personal_get_notebooks."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "section_id": {"type": "string", "description": "OneNote section ID to add the page to"},
                        "title": {"type": "string", "description": "Page title"},
                        "content": {"type": "string", "description": "Page content (plain text or HTML)"},
                    },
                    "required": ["user_id", "section_id", "title", "content"],
                },
                "handler": self._create_note,
            },
            # ── Teams tools ────────────────────────────────────────────────
            {
                "name": "personal_get_chats",
                "description": "List the user's personal Microsoft Teams chats (1:1 and group chats).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max chats to return. Default: 20",
                            "default": 20,
                        },
                    },
                    "required": ["user_id"],
                },
                "handler": self._get_chats,
            },
            {
                "name": "personal_get_chat_messages",
                "description": "Get messages from a specific Teams chat.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "chat_id": {"type": "string", "description": "Teams chat ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max messages to return. Default: 20",
                            "default": 20,
                        },
                    },
                    "required": ["user_id", "chat_id"],
                },
                "handler": self._get_chat_messages,
            },
            {
                "name": "personal_send_chat_message",
                "description": "Send a message to a Teams chat on behalf of the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "chat_id": {"type": "string", "description": "Teams chat ID"},
                        "message": {"type": "string", "description": "Message text to send"},
                    },
                    "required": ["user_id", "chat_id", "message"],
                },
                "handler": self._send_chat_message,
            },
            {
                "name": "personal_get_teams",
                "description": "List the Teams the user has joined in their personal Microsoft account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                    },
                    "required": ["user_id"],
                },
                "handler": self._get_teams,
            },
            {
                "name": "personal_get_channel_messages",
                "description": "Get messages from a Teams channel the user belongs to.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "team_id": {"type": "string", "description": "Teams team ID"},
                        "channel_id": {"type": "string", "description": "Teams channel ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max messages to return. Default: 20",
                            "default": 20,
                        },
                    },
                    "required": ["user_id", "team_id", "channel_id"],
                },
                "handler": self._get_channel_messages,
            },
            # ── Contacts tools ─────────────────────────────────────────────
            {
                "name": "personal_get_contacts",
                "description": (
                    "List contacts from the user's personal Microsoft account. "
                    "Returns displayName, email addresses, phone, job title, and company."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max contacts to return (1-50). Default: 20",
                            "default": 20,
                        },
                    },
                    "required": ["user_id"],
                },
                "handler": self._get_contacts,
            },
            {
                "name": "personal_search_contacts",
                "description": (
                    "Search the user's Microsoft contacts by name or email address."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "query": {"type": "string", "description": "Name or email to search for"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (1-50). Default: 10",
                            "default": 10,
                        },
                    },
                    "required": ["user_id", "query"],
                },
                "handler": self._search_contacts,
            },
            {
                "name": "personal_get_contact_detail",
                "description": "Get full details of a specific contact by their Graph contact ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "contact_id": {"type": "string", "description": "Graph API contact ID"},
                    },
                    "required": ["user_id", "contact_id"],
                },
                "handler": self._get_contact_detail,
            },
            {
                "name": "personal_create_contact",
                "description": (
                    "Create a new contact in the user's personal Microsoft account."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                        "display_name": {"type": "string", "description": "Contact's full name"},
                        "email": {"type": "string", "description": "Primary email address. Optional."},
                        "phone": {"type": "string", "description": "Mobile phone number. Optional."},
                        "company": {"type": "string", "description": "Company name. Optional."},
                        "job_title": {"type": "string", "description": "Job title. Optional."},
                    },
                    "required": ["user_id", "display_name"],
                },
                "handler": self._create_contact,
            },
            # ── Diagnostic tool ────────────────────────────────────────────
            {
                "name": "personal_check_token_scopes",
                "description": (
                    "Check what Microsoft Graph permissions are currently granted in the "
                    "user's connected account token. Use this to diagnose why MS tools "
                    "might be failing (e.g., missing write permissions)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "The current user's ID"},
                    },
                    "required": ["user_id"],
                },
                "handler": self._check_token_scopes,
            },
        ]

    # ── Email handlers ───────────────────────────────────────────────────────

    async def _read_emails(self, user_id: str, folder: str = "inbox", limit: int = 10, filter: str = None) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        limit = min(max(1, limit), 50)
        url = f"{_GRAPH_BASE}/me/mailFolders/{folder}/messages"
        params = {
            "$top": limit,
            "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
            "$orderby": "receivedDateTime desc",
        }
        if filter:
            params["$filter"] = filter

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        emails = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_read_emails", "mail", {"folder": folder, "limit": limit})
        return self._ok({"folder": folder, "count": len(emails), "emails": emails})

    async def _search_emails(self, user_id: str, query: str, limit: int = 10) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        limit = min(max(1, limit), 50)
        url = f"{_GRAPH_BASE}/me/messages"
        params = {
            "$search": f'"{query}"',
            "$top": limit,
            "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        emails = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_search_emails", "mail", {"query": query})
        return self._ok({"query": query, "count": len(emails), "emails": emails})

    async def _send_email(
        self, user_id: str, to: list, subject: str, body: str,
        cc: list = None, is_html: bool = False,
    ) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        content_type = "html" if is_html else "text"
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": content_type, "content": body},
                "toRecipients": [{"emailAddress": {"address": a}} for a in to],
            },
            "saveToSentItems": True,
        }
        if cc:
            payload["message"]["ccRecipients"] = [{"emailAddress": {"address": a}} for a in cc]

        url = f"{_GRAPH_BASE}/me/sendMail"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code not in (200, 202):
            logger.error(
                f"personal_ms WRITE FAILED | tool=personal_send_email user_id={user_id} "
                f"status={resp.status_code} body={resp.text[:500]}"
            )
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        await self._audit(user_id, "personal_ms_send_email", "mail", {"to": to, "subject": subject})
        return self._ok({"sent": True, "to": to, "subject": subject})

    async def _get_email_detail(self, user_id: str, message_id: str) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/messages/{message_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        await self._audit(user_id, "personal_ms_get_email_detail", "mail", {"message_id": message_id})
        return self._ok(resp.json())

    # ── Calendar handlers ────────────────────────────────────────────────────

    async def _get_events(self, user_id: str, start: str, end: str, limit: int = 20) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        # calendarView requires Prefer: outlook.timezone header for local times
        headers["Prefer"] = 'outlook.timezone="UTC"'
        url = f"{_GRAPH_BASE}/me/calendarView"
        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$top": min(max(1, limit), 50),
            "$select": "id,subject,start,end,location,organizer,attendees,isOnlineMeeting,onlineMeetingUrl",
            "$orderby": "start/dateTime",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        events = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_get_events", "calendar", {"start": start, "end": end})
        return self._ok({"count": len(events), "events": events})

    async def _create_event(
        self, user_id: str, subject: str, start: str, end: str,
        body: str = None, attendees: list = None, location: str = None,
        is_online: bool = False,
    ) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        payload = {
            "subject": subject,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if body:
            payload["body"] = {"contentType": "text", "content": body}
        if location:
            payload["location"] = {"displayName": location}
        if attendees:
            payload["attendees"] = [
                {"emailAddress": {"address": a}, "type": "required"} for a in attendees
            ]
        if is_online:
            payload["isOnlineMeeting"] = True
            payload["onlineMeetingProvider"] = "teamsForBusiness"

        url = f"{_GRAPH_BASE}/me/events"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code not in (200, 201):
            logger.error(
                f"personal_ms WRITE FAILED | tool=personal_create_event user_id={user_id} "
                f"status={resp.status_code} body={resp.text[:500]}"
            )
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        event = resp.json()
        await self._audit(user_id, "personal_ms_create_event", "calendar", {"subject": subject, "start": start})
        return self._ok({"created": True, "event_id": event.get("id"), "subject": subject})

    async def _update_event(
        self, user_id: str, event_id: str, subject: str = None,
        start: str = None, end: str = None, body: str = None, location: str = None,
    ) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        payload = {}
        if subject:
            payload["subject"] = subject
        if start:
            payload["start"] = {"dateTime": start, "timeZone": "UTC"}
        if end:
            payload["end"] = {"dateTime": end, "timeZone": "UTC"}
        if body:
            payload["body"] = {"contentType": "text", "content": body}
        if location:
            payload["location"] = {"displayName": location}

        if not payload:
            return self._err("No fields provided to update")

        url = f"{_GRAPH_BASE}/me/events/{event_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(url, headers=headers, json=payload)

        if resp.status_code not in (200, 204):
            logger.error(
                f"personal_ms WRITE FAILED | tool=personal_update_event user_id={user_id} "
                f"status={resp.status_code} body={resp.text[:500]}"
            )
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        await self._audit(user_id, "personal_ms_update_event", "calendar", {"event_id": event_id})
        return self._ok({"updated": True, "event_id": event_id})

    async def _delete_event(self, user_id: str, event_id: str) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/events/{event_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(url, headers=headers)

        if resp.status_code not in (204, 200):
            logger.error(
                f"personal_ms WRITE FAILED | tool=personal_delete_event user_id={user_id} "
                f"status={resp.status_code} body={resp.text[:500]}"
            )
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        await self._audit(user_id, "personal_ms_delete_event", "calendar", {"event_id": event_id})
        return self._ok({"deleted": True, "event_id": event_id})

    async def _find_free_slots(
        self, user_id: str, start: str, end: str, min_duration_minutes: int = 30,
    ) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        from datetime import datetime, timezone, timedelta
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        headers["Prefer"] = 'outlook.timezone="UTC"'
        url = f"{_GRAPH_BASE}/me/calendarView"
        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$select": "start,end",
            "$orderby": "start/dateTime",
            "$top": 50,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        events = resp.json().get("value", [])
        min_delta = timedelta(minutes=min_duration_minutes)

        # Parse range boundaries
        range_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        range_end = datetime.fromisoformat(end.replace("Z", "+00:00"))

        # Build busy intervals
        busy = []
        for ev in events:
            ev_start = datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00"))
            ev_end = datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00"))
            busy.append((ev_start, ev_end))

        # Find gaps
        free_slots = []
        cursor = range_start
        for b_start, b_end in sorted(busy):
            if cursor < b_start and (b_start - cursor) >= min_delta:
                free_slots.append({
                    "start": cursor.isoformat(),
                    "end": b_start.isoformat(),
                    "duration_minutes": int((b_start - cursor).total_seconds() / 60),
                })
            cursor = max(cursor, b_end)
        # Check gap after last event
        if cursor < range_end and (range_end - cursor) >= min_delta:
            free_slots.append({
                "start": cursor.isoformat(),
                "end": range_end.isoformat(),
                "duration_minutes": int((range_end - cursor).total_seconds() / 60),
            })

        await self._audit(user_id, "personal_ms_find_free_slots", "calendar", {"start": start, "end": end})
        return self._ok({
            "range_start": start,
            "range_end": end,
            "min_duration_minutes": min_duration_minutes,
            "free_slot_count": len(free_slots),
            "free_slots": free_slots,
        })

    # ── Notes handlers ───────────────────────────────────────────────────────

    async def _get_notebooks(self, user_id: str) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/onenote/notebooks"
        params = {"$expand": "sections", "$select": "id,displayName,sections"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        notebooks = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_get_notebooks", "onenote", {})
        return self._ok({"count": len(notebooks), "notebooks": notebooks})

    async def _get_notes(self, user_id: str, limit: int = 20) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/onenote/pages"
        params = {
            "$top": min(max(1, limit), 50),
            "$select": "id,title,createdDateTime,lastModifiedDateTime,parentSection",
            "$orderby": "lastModifiedDateTime desc",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        pages = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_get_notes", "onenote", {"limit": limit})
        return self._ok({"count": len(pages), "pages": pages})

    async def _search_notes(self, user_id: str, query: str, limit: int = 10) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/onenote/pages"
        params = {
            "$search": f'"{query}"',
            "$top": min(max(1, limit), 50),
            "$select": "id,title,createdDateTime,lastModifiedDateTime,parentSection",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        pages = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_search_notes", "onenote", {"query": query})
        return self._ok({"query": query, "count": len(pages), "pages": pages})

    async def _create_note(self, user_id: str, section_id: str, title: str, content: str) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            # OneNote create page uses text/html content type
            token_headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        html_headers = {
            "Authorization": token_headers["Authorization"],
            "Content-Type": "application/xhtml+xml",
        }

        # Wrap plain text content in minimal XHTML
        if not content.strip().startswith("<"):
            html_body = f"<html><head><title>{title}</title></head><body><p>{content}</p></body></html>"
        else:
            html_body = content

        url = f"{_GRAPH_BASE}/me/onenote/sections/{section_id}/pages"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=html_headers, content=html_body.encode())

        if resp.status_code not in (200, 201):
            logger.error(
                f"personal_ms WRITE FAILED | tool=personal_create_note user_id={user_id} "
                f"status={resp.status_code} body={resp.text[:500]}"
            )
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        page = resp.json()
        await self._audit(user_id, "personal_ms_create_note", "onenote", {"title": title, "section_id": section_id})
        return self._ok({"created": True, "page_id": page.get("id"), "title": title})

    # ── Teams handlers ───────────────────────────────────────────────────────

    async def _get_chats(self, user_id: str, limit: int = 20) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/chats"
        params = {
            "$top": min(max(1, limit), 50),
            "$select": "id,chatType,topic,lastUpdatedDateTime",
            "$orderby": "lastUpdatedDateTime desc",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        chats = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_get_chats", "teams", {})
        return self._ok({"count": len(chats), "chats": chats})

    async def _get_chat_messages(self, user_id: str, chat_id: str, limit: int = 20) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/chats/{chat_id}/messages"
        params = {
            "$top": min(max(1, limit), 50),
            "$select": "id,body,from,createdDateTime,messageType",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        messages = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_get_chat_messages", "teams", {"chat_id": chat_id})
        return self._ok({"chat_id": chat_id, "count": len(messages), "messages": messages})

    async def _send_chat_message(self, user_id: str, chat_id: str, message: str) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/chats/{chat_id}/messages"
        payload = {"body": {"content": message, "contentType": "text"}}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code not in (200, 201):
            logger.error(
                f"personal_ms WRITE FAILED | tool=personal_send_chat_message user_id={user_id} "
                f"status={resp.status_code} body={resp.text[:500]}"
            )
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        result = resp.json()
        await self._audit(user_id, "personal_ms_send_chat_message", "teams", {"chat_id": chat_id})
        return self._ok({"sent": True, "message_id": result.get("id"), "chat_id": chat_id})

    async def _get_teams(self, user_id: str) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/joinedTeams"
        params = {"$select": "id,displayName,description,visibility"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        teams = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_get_teams", "teams", {})
        return self._ok({"count": len(teams), "teams": teams})

    async def _get_channel_messages(
        self, user_id: str, team_id: str, channel_id: str, limit: int = 20,
    ) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        # Channel messages use /teams/{id}/channels/{id}/messages (not /me/)
        url = f"{_GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages"
        params = {
            "$top": min(max(1, limit), 50),
            "$select": "id,body,from,createdDateTime,messageType",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        messages = resp.json().get("value", [])
        await self._audit(
            user_id, "personal_ms_get_channel_messages", "teams",
            {"team_id": team_id, "channel_id": channel_id},
        )
        return self._ok({
            "team_id": team_id,
            "channel_id": channel_id,
            "count": len(messages),
            "messages": messages,
        })

    # ── Contacts handlers ─────────────────────────────────────────────────────

    async def _get_contacts(self, user_id: str, limit: int = 20) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        limit = min(max(1, limit), 50)
        url = f"{_GRAPH_BASE}/me/contacts"
        params = {
            "$top": limit,
            "$select": "id,displayName,emailAddresses,mobilePhone,jobTitle,companyName",
            "$orderby": "displayName",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        contacts = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_get_contacts", "contacts", {"limit": limit})
        return self._ok({"count": len(contacts), "contacts": contacts})

    async def _search_contacts(self, user_id: str, query: str, limit: int = 10) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        limit = min(max(1, limit), 50)
        url = f"{_GRAPH_BASE}/me/contacts"
        params = {
            "$search": f'"{query}"',
            "$top": limit,
            "$select": "id,displayName,emailAddresses,mobilePhone,jobTitle,companyName",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        contacts = resp.json().get("value", [])
        await self._audit(user_id, "personal_ms_search_contacts", "contacts", {"query": query})
        return self._ok({"query": query, "count": len(contacts), "contacts": contacts})

    async def _get_contact_detail(self, user_id: str, contact_id: str) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        url = f"{_GRAPH_BASE}/me/contacts/{contact_id}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        await self._audit(user_id, "personal_ms_get_contact_detail", "contacts", {"contact_id": contact_id})
        return self._ok(resp.json())

    async def _create_contact(
        self, user_id: str, display_name: str,
        email: str = None, phone: str = None,
        company: str = None, job_title: str = None,
    ) -> dict:
        from app.services.ms_token_service import MSNotConnectedException
        import httpx
        try:
            headers = await self._get_headers(user_id)
        except MSNotConnectedException:
            return self._not_connected()

        payload: dict = {"displayName": display_name}
        if email:
            payload["emailAddresses"] = [{"address": email, "name": display_name}]
        if phone:
            payload["mobilePhone"] = phone
        if company:
            payload["companyName"] = company
        if job_title:
            payload["jobTitle"] = job_title

        url = f"{_GRAPH_BASE}/me/contacts"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code not in (200, 201):
            logger.error(
                f"personal_ms WRITE FAILED | tool=personal_create_contact user_id={user_id} "
                f"status={resp.status_code} body={resp.text[:500]}"
            )
            return self._err(f"Graph API error {resp.status_code}: {resp.text[:200]}")

        contact = resp.json()
        await self._audit(user_id, "personal_ms_create_contact", "contacts", {"display_name": display_name})
        return self._ok({"created": True, "contact_id": contact.get("id"), "display_name": display_name})

    # ── Diagnostic handler ────────────────────────────────────────────────────

    async def _check_token_scopes(self, user_id: str) -> dict:
        """
        Decode the stored access token (without signature verification) and return
        the granted scopes (scp claim) + the Microsoft account UPN.

        Useful for diagnosing whether write permissions are present in the token.
        """
        import base64
        from app.services.ms_token_service import MSNotConnectedException
        try:
            token = await self._get_raw_token(user_id)
        except MSNotConnectedException:
            return self._not_connected()
        except Exception as e:
            return self._err(f"Could not retrieve token: {e}")

        try:
            # JWT = header.payload.signature — decode the payload segment
            parts = token.split(".")
            if len(parts) != 3:
                return self._err("Stored token is not a valid JWT")

            # Base64url decode with padding fix
            payload_b64 = parts[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            claims = json.loads(payload_bytes.decode("utf-8"))

            scp_raw: str = claims.get("scp", "")
            scopes = scp_raw.split() if scp_raw else []

            ms_account = (
                claims.get("upn")
                or claims.get("unique_name")
                or claims.get("preferred_username")
                or claims.get("email")
                or "unknown"
            )

            # Identify important missing write scopes
            write_scopes = {"Mail.Send", "Calendars.ReadWrite", "Notes.ReadWrite", "Chat.ReadWrite"}
            missing = sorted(write_scopes - set(scopes))

            return self._ok({
                "token_present": True,
                "ms_account": ms_account,
                "granted_scopes": sorted(scopes),
                "missing_write_scopes": missing,
                "diagnosis": (
                    "All write scopes present — write operations should work."
                    if not missing
                    else f"MISSING write scopes: {', '.join(missing)}. "
                         "Disconnect and reconnect your Microsoft account in Settings → Connected Accounts "
                         "after ensuring these permissions are registered in your Azure AD app."
                ),
            })
        except Exception as e:
            return self._err(f"Failed to decode token: {e}")

    async def _get_raw_token(self, user_id: str) -> str:
        """Return the raw access token string for the given user."""
        from app.services.ms_token_service import get_valid_token
        return await get_valid_token(user_id)
