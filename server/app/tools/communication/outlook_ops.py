"""
Outlook Tool — MS Graph API for email and calendar operations.

Tools provided:
    outlook_send_email     — Send HTML email via Microsoft Graph
    outlook_read_emails    — Read inbox with filters
    outlook_batch_send     — Send personalized emails to a list
    outlook_reply_email    — Reply to an existing email thread
    outlook_search_emails  — Search emails by keyword
    outlook_create_event   — Create a calendar event
    outlook_get_events     — Read calendar events for a date range
    outlook_find_free_slots — Find available time slots

Config required (config.yaml → ms365):
    tenant_id, client_id, client_secret, sender_email

Email rate limit: 30 emails/hour (Microsoft policy).
All sent emails are logged to audit_log.
"""

import logging
import os
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.outlook")

# Microsoft Graph base URL
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_graph_client(config: dict):
    """Build an authenticated MS Graph client using app credentials."""
    from azure.identity.aio import ClientSecretCredential
    from msgraph import GraphServiceClient

    ms365 = config.get("ms365", {})
    credential = ClientSecretCredential(
        tenant_id=ms365.get("tenant_id") or os.getenv("MS365_TENANT_ID", ""),
        client_id=ms365.get("client_id") or os.getenv("MS365_CLIENT_ID", ""),
        client_secret=ms365.get("client_secret") or os.getenv("MS365_CLIENT_SECRET", ""),
    )
    return GraphServiceClient(
        credentials=credential,
        scopes=["https://graph.microsoft.com/.default"],
    )


def _build_attachment(attachment: dict) -> dict:
    """Convert attachment spec to Graph API format."""
    import base64
    data = attachment.get("data", b"")
    if isinstance(data, str):
        data = data.encode()
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": attachment.get("name", "attachment"),
        "contentType": attachment.get("content_type", "application/octet-stream"),
        "contentBytes": base64.b64encode(data).decode(),
    }


class OutlookOps(BaseTool):

    def __init__(self, config: dict):
        super().__init__(config)
        self._sender = (
            config.get("ms365", {}).get("sender_email")
            or os.getenv("MS365_SENDER_EMAIL", "ai-assistant@mezzofy.com")
        )

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "outlook_send_email",
                "description": "Send an HTML email via Microsoft Outlook. Use for formal communications, reports, and notifications. Supports CC, BCC, and file attachments (PDF, PPTX, CSV).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient email address(es)"},
                        "subject": {"type": "string", "description": "Email subject line"},
                        "body_html": {"type": "string", "description": "Email body as HTML"},
                        "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients (optional)"},
                        "bcc": {"type": "array", "items": {"type": "string"}, "description": "BCC recipients (optional)"},
                        "attachments": {
                            "type": "array",
                            "description": "File attachments (optional)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "data": {"type": "string", "description": "Base64-encoded file content"},
                                    "content_type": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["to", "subject", "body_html"],
                },
                "handler": self._send_email,
            },
            {
                "name": "outlook_read_emails",
                "description": "Read emails from a user's Outlook inbox. Can filter by sender, subject, date range, or folder. Returns up to 20 most recent matching emails.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_email": {"type": "string", "description": "The mailbox to read from"},
                        "folder": {"type": "string", "description": "Folder name (default: Inbox)", "default": "Inbox"},
                        "from_sender": {"type": "string", "description": "Filter by sender email (optional)"},
                        "subject_contains": {"type": "string", "description": "Filter by subject keyword (optional)"},
                        "limit": {"type": "integer", "description": "Max emails to return (default: 10, max: 20)", "default": 10},
                    },
                    "required": ["user_email"],
                },
                "handler": self._read_emails,
            },
            {
                "name": "outlook_batch_send",
                "description": "Send personalized emails to multiple recipients. Each recipient gets a customized version with their name/company substituted. Rate-limited to 30/hour.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipients": {
                            "type": "array",
                            "description": "List of recipients with personalization data",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"},
                                    "name": {"type": "string"},
                                    "variables": {"type": "object", "description": "Custom template variables"},
                                },
                                "required": ["email"],
                            },
                        },
                        "subject_template": {"type": "string", "description": "Subject with {name}, {company} placeholders"},
                        "body_html_template": {"type": "string", "description": "HTML body with {name}, {company} placeholders"},
                    },
                    "required": ["recipients", "subject_template", "body_html_template"],
                },
                "handler": self._batch_send,
            },
            {
                "name": "outlook_reply_email",
                "description": "Reply to an existing email thread by message ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_email": {"type": "string", "description": "The mailbox to reply from"},
                        "message_id": {"type": "string", "description": "The ID of the message to reply to"},
                        "reply_body_html": {"type": "string", "description": "Reply content as HTML"},
                    },
                    "required": ["user_email", "message_id", "reply_body_html"],
                },
                "handler": self._reply_email,
            },
            {
                "name": "outlook_search_emails",
                "description": "Search emails by keyword across all folders in a mailbox.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_email": {"type": "string", "description": "The mailbox to search"},
                        "query": {"type": "string", "description": "Search keyword or phrase"},
                        "limit": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
                    },
                    "required": ["user_email", "query"],
                },
                "handler": self._search_emails,
            },
            {
                "name": "outlook_create_event",
                "description": "Create a calendar event (meeting, reminder, deadline) in Outlook. Timezone defaults to Asia/Singapore.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_email": {"type": "string", "description": "Calendar owner's email"},
                        "subject": {"type": "string", "description": "Event title"},
                        "start": {"type": "string", "description": "Start datetime (ISO 8601, e.g. 2026-03-15T14:00:00)"},
                        "end": {"type": "string", "description": "End datetime (ISO 8601)"},
                        "body": {"type": "string", "description": "Event description/agenda (optional)"},
                        "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses (optional)"},
                        "is_online_meeting": {"type": "boolean", "description": "Create Teams meeting link (default: false)", "default": False},
                    },
                    "required": ["user_email", "subject", "start", "end"],
                },
                "handler": self._create_event,
            },
            {
                "name": "outlook_get_events",
                "description": "Read calendar events for a user within a date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_email": {"type": "string", "description": "Calendar owner's email"},
                        "start_date": {"type": "string", "description": "Start of date range (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End of date range (YYYY-MM-DD)"},
                    },
                    "required": ["user_email", "start_date", "end_date"],
                },
                "handler": self._get_events,
            },
            {
                "name": "outlook_find_free_slots",
                "description": "Find available meeting time slots for a user on a given date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_email": {"type": "string", "description": "The user to check availability for"},
                        "date": {"type": "string", "description": "Date to check (YYYY-MM-DD)"},
                        "duration_minutes": {"type": "integer", "description": "Required meeting duration in minutes", "default": 30},
                    },
                    "required": ["user_email", "date"],
                },
                "handler": self._find_free_slots,
            },
        ]

    # ── Email Handlers ────────────────────────────────────────────────────────

    async def _send_email(
        self,
        to: list[str],
        subject: str,
        body_html: str,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        attachments: Optional[list[dict]] = None,
    ) -> dict:
        try:
            from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
            from msgraph.generated.models.message import Message
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.body_type import BodyType
            from msgraph.generated.models.recipient import Recipient
            from msgraph.generated.models.email_address import EmailAddress

            client = _get_graph_client(self.config)

            def _recipient(addr: str) -> Recipient:
                r = Recipient()
                r.email_address = EmailAddress()
                r.email_address.address = addr
                return r

            message = Message()
            message.subject = subject
            message.body = ItemBody()
            message.body.content_type = BodyType.Html
            # Append standard footer
            footer = "<br><br><small>Sent via Mezzofy AI Assistant</small>"
            message.body.content = body_html + footer
            message.to_recipients = [_recipient(addr) for addr in to]
            if cc:
                message.cc_recipients = [_recipient(addr) for addr in cc]
            if bcc:
                message.bcc_recipients = [_recipient(addr) for addr in bcc]
            if attachments:
                from msgraph.generated.models.file_attachment import FileAttachment
                import base64
                att_list = []
                for a in attachments:
                    fa = FileAttachment()
                    fa.name = a.get("name", "attachment")
                    fa.content_type = a.get("content_type", "application/octet-stream")
                    data = a.get("data", b"")
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    fa.content_bytes = data
                    att_list.append(fa)
                message.attachments = att_list

            request_body = SendMailPostRequestBody()
            request_body.message = message
            request_body.save_to_sent_items = True

            await client.users.by_user_id(self._sender).send_mail.post(body=request_body)

            logger.info(f"Email sent to {to} — subject: {subject}")
            return self._ok({
                "sent_to": to,
                "subject": subject,
                "from": self._sender,
            })
        except Exception as e:
            logger.error(f"outlook_send_email failed: {e}")
            return self._err(f"Failed to send email: {e}")

    async def _read_emails(
        self,
        user_email: str,
        folder: str = "Inbox",
        from_sender: Optional[str] = None,
        subject_contains: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        try:
            client = _get_graph_client(self.config)
            limit = min(limit, 20)

            # Build OData filter
            filters = []
            if from_sender:
                filters.append(f"from/emailAddress/address eq '{from_sender}'")
            if subject_contains:
                filters.append(f"contains(subject, '{subject_contains}')")
            filter_str = " and ".join(filters) if filters else None

            from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import MessagesRequestBuilderGetQueryParameters
            from kiota_abstractions.base_request_configuration import RequestConfiguration

            query_params = MessagesRequestBuilderGetQueryParameters(
                top=limit,
                select=["id", "subject", "from", "receivedDateTime", "bodyPreview", "isRead"],
                filter=filter_str,
                order_by=["receivedDateTime DESC"],
            )
            config = RequestConfiguration(query_parameters=query_params)

            result = await (
                client.users.by_user_id(user_email)
                .mail_folders.by_mail_folder_id(folder)
                .messages
                .get(request_configuration=config)
            )

            emails = []
            if result and result.value:
                for msg in result.value:
                    emails.append({
                        "id": msg.id,
                        "subject": msg.subject,
                        "from": msg.from_.email_address.address if msg.from_ else None,
                        "received": msg.received_date_time.isoformat() if msg.received_date_time else None,
                        "preview": msg.body_preview,
                        "is_read": msg.is_read,
                    })

            return self._ok({"emails": emails, "count": len(emails)})
        except Exception as e:
            logger.error(f"outlook_read_emails failed: {e}")
            return self._err(f"Failed to read emails: {e}")

    async def _batch_send(
        self,
        recipients: list[dict],
        subject_template: str,
        body_html_template: str,
    ) -> dict:
        """Send personalized emails to a list. Rate-limited: 30/hour."""
        import asyncio
        sent = []
        failed = []
        rate_limit = self.config.get("ms365", {}).get("rate_limit_emails_per_hour", 30)

        for i, recipient in enumerate(recipients):
            if i >= rate_limit:
                failed.append({"email": recipient["email"], "reason": "Rate limit reached"})
                continue

            variables = recipient.get("variables", {})
            variables.setdefault("name", recipient.get("name", ""))
            variables.setdefault("email", recipient["email"])

            subject = subject_template.format(**variables)
            body_html = body_html_template.format(**variables)

            result = await self._send_email(
                to=[recipient["email"]],
                subject=subject,
                body_html=body_html,
            )
            if result["success"]:
                sent.append(recipient["email"])
            else:
                failed.append({"email": recipient["email"], "reason": result.get("error")})

            # Small delay to avoid bursting Microsoft rate limits
            if i < len(recipients) - 1:
                await asyncio.sleep(1.2)

        return self._ok({
            "sent_count": len(sent),
            "failed_count": len(failed),
            "sent": sent,
            "failed": failed,
        })

    async def _reply_email(
        self,
        user_email: str,
        message_id: str,
        reply_body_html: str,
    ) -> dict:
        try:
            from msgraph.generated.users.item.messages.item.reply.reply_post_request_body import ReplyPostRequestBody
            from msgraph.generated.models.message import Message
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.body_type import BodyType

            client = _get_graph_client(self.config)

            reply_message = Message()
            reply_message.body = ItemBody()
            reply_message.body.content_type = BodyType.Html
            reply_message.body.content = reply_body_html

            request_body = ReplyPostRequestBody()
            request_body.message = reply_message

            await (
                client.users.by_user_id(user_email)
                .messages.by_message_id(message_id)
                .reply.post(body=request_body)
            )
            return self._ok({"replied_to": message_id})
        except Exception as e:
            return self._err(f"Failed to reply to email: {e}")

    async def _search_emails(self, user_email: str, query: str, limit: int = 10) -> dict:
        try:
            client = _get_graph_client(self.config)
            limit = min(limit, 20)

            from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilderGetQueryParameters
            from kiota_abstractions.base_request_configuration import RequestConfiguration

            query_params = MessagesRequestBuilderGetQueryParameters(
                top=limit,
                search=f'"{query}"',
                select=["id", "subject", "from", "receivedDateTime", "bodyPreview"],
            )
            config = RequestConfiguration(query_parameters=query_params)
            result = await client.users.by_user_id(user_email).messages.get(request_configuration=config)

            emails = []
            if result and result.value:
                for msg in result.value:
                    emails.append({
                        "id": msg.id,
                        "subject": msg.subject,
                        "from": msg.from_.email_address.address if msg.from_ else None,
                        "received": msg.received_date_time.isoformat() if msg.received_date_time else None,
                        "preview": msg.body_preview,
                    })
            return self._ok({"emails": emails, "count": len(emails)})
        except Exception as e:
            return self._err(f"Failed to search emails: {e}")

    # ── Calendar Handlers ────────────────────────────────────────────────────

    async def _create_event(
        self,
        user_email: str,
        subject: str,
        start: str,
        end: str,
        body: Optional[str] = None,
        attendees: Optional[list[str]] = None,
        is_online_meeting: bool = False,
    ) -> dict:
        try:
            from msgraph.generated.models.event import Event
            from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.body_type import BodyType
            from msgraph.generated.models.attendee import Attendee
            from msgraph.generated.models.email_address import EmailAddress
            from msgraph.generated.models.attendee_type import AttendeeType

            client = _get_graph_client(self.config)
            tz = self.config.get("ms365", {}).get("calendar_default_timezone", "Asia/Singapore")

            event = Event()
            event.subject = subject
            event.start = DateTimeTimeZone()
            event.start.date_time = start
            event.start.time_zone = tz
            event.end = DateTimeTimeZone()
            event.end.date_time = end
            event.end.time_zone = tz
            event.is_online_meeting = is_online_meeting

            if body:
                event.body = ItemBody()
                event.body.content_type = BodyType.Html
                event.body.content = body

            if attendees:
                att_list = []
                for email_addr in attendees:
                    att = Attendee()
                    att.email_address = EmailAddress()
                    att.email_address.address = email_addr
                    att.type = AttendeeType.Required
                    att_list.append(att)
                event.attendees = att_list

            created = await client.users.by_user_id(user_email).events.post(body=event)

            return self._ok({
                "event_id": created.id if created else None,
                "subject": subject,
                "start": start,
                "end": end,
                "attendees": attendees or [],
            })
        except Exception as e:
            return self._err(f"Failed to create calendar event: {e}")

    async def _get_events(self, user_email: str, start_date: str, end_date: str) -> dict:
        try:
            from msgraph.generated.users.item.calendar_view.calendar_view_request_builder import CalendarViewRequestBuilderGetQueryParameters
            from kiota_abstractions.base_request_configuration import RequestConfiguration

            client = _get_graph_client(self.config)

            query_params = CalendarViewRequestBuilderGetQueryParameters(
                start_date_time=f"{start_date}T00:00:00",
                end_date_time=f"{end_date}T23:59:59",
                select=["id", "subject", "start", "end", "attendees", "isOnlineMeeting"],
                top=50,
            )
            config = RequestConfiguration(query_parameters=query_params)
            result = await client.users.by_user_id(user_email).calendar_view.get(request_configuration=config)

            events = []
            if result and result.value:
                for ev in result.value:
                    events.append({
                        "id": ev.id,
                        "subject": ev.subject,
                        "start": ev.start.date_time if ev.start else None,
                        "end": ev.end.date_time if ev.end else None,
                        "is_online": ev.is_online_meeting,
                    })
            return self._ok({"events": events, "count": len(events)})
        except Exception as e:
            return self._err(f"Failed to get calendar events: {e}")

    async def _find_free_slots(
        self,
        user_email: str,
        date: str,
        duration_minutes: int = 30,
    ) -> dict:
        """Find available time slots by checking calendar for the day."""
        result = await self._get_events(user_email, date, date)
        if not result["success"]:
            return result

        events = result["output"]["events"]
        # Build busy intervals
        busy = []
        for ev in events:
            if ev["start"] and ev["end"]:
                start_t = ev["start"][:16]  # YYYY-MM-DDTHH:MM
                end_t = ev["end"][:16]
                busy.append((start_t, end_t))

        # Find free slots in business hours (09:00–18:00)
        from datetime import datetime, timedelta
        day_start = datetime.strptime(f"{date}T09:00", "%Y-%m-%dT%H:%M")
        day_end = datetime.strptime(f"{date}T18:00", "%Y-%m-%dT%H:%M")
        slot_duration = timedelta(minutes=duration_minutes)

        free_slots = []
        current = day_start
        while current + slot_duration <= day_end:
            slot_end = current + slot_duration
            slot_str_start = current.strftime("%H:%M")
            slot_str_end = slot_end.strftime("%H:%M")
            is_free = not any(
                b[0][:16] < slot_end.strftime("%Y-%m-%dT%H:%M") and
                b[1][:16] > current.strftime("%Y-%m-%dT%H:%M")
                for b in busy
            )
            if is_free:
                free_slots.append({"start": slot_str_start, "end": slot_str_end})
            current += timedelta(minutes=30)

        return self._ok({
            "date": date,
            "duration_minutes": duration_minutes,
            "free_slots": free_slots[:8],  # Return up to 8 slots
        })
