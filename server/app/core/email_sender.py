"""
Transactional Email Sender — thin MS Graph wrapper for auth emails.

This module is intentionally separate from OutlookOps (the agent tool).
Auth emails (OTP codes, password resets) must not depend on the agent
framework — they need to work during login before any agent context exists.

Config: reads ms365.tenant_id / client_id / client_secret / sender_email
from get_config(), same source as OutlookOps.

Usage:
    await send_transactional_email(
        to="user@example.com",
        subject="Your Mezzofy Login Code",
        body_html="<p>Your code is <strong>123456</strong></p>",
    )
"""

import logging
import os

from app.core.config import get_config

logger = logging.getLogger("mezzofy.core.email_sender")


async def send_transactional_email(to: str, subject: str, body_html: str) -> None:
    """
    Send a transactional HTML email via MS Graph.

    Reads MS365 credentials from config.yaml / environment variables.
    Raises RuntimeError if the send fails.
    """
    from azure.identity.aio import ClientSecretCredential
    from msgraph import GraphServiceClient
    from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
        SendMailPostRequestBody,
    )
    from msgraph.generated.models.message import Message
    from msgraph.generated.models.item_body import ItemBody
    from msgraph.generated.models.body_type import BodyType
    from msgraph.generated.models.recipient import Recipient
    from msgraph.generated.models.email_address import EmailAddress

    config = get_config()
    ms365 = config.get("ms365", {})

    tenant_id = ms365.get("tenant_id") or os.getenv("MS365_TENANT_ID", "")
    client_id = ms365.get("client_id") or os.getenv("MS365_CLIENT_ID", "")
    client_secret = ms365.get("client_secret") or os.getenv("MS365_CLIENT_SECRET", "")
    sender_email = (
        ms365.get("sender_email")
        or os.getenv("MS365_SENDER_EMAIL", "ai-assistant@mezzofy.com")
    )

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    graph_client = GraphServiceClient(
        credentials=credential,
        scopes=["https://graph.microsoft.com/.default"],
    )

    message = Message(
        subject=subject,
        body=ItemBody(content_type=BodyType.Html, content=body_html),
        to_recipients=[
            Recipient(email_address=EmailAddress(address=to))
        ],
    )
    request_body = SendMailPostRequestBody(message=message, save_to_sent_items=False)

    try:
        await graph_client.users.by_user_id(sender_email).send_mail.post(request_body)
        logger.info(f"Transactional email sent to {to} — subject: {subject}")
    except Exception as exc:
        logger.error(f"Failed to send transactional email to {to}: {exc}")
        raise RuntimeError(f"Email send failed: {exc}") from exc
    finally:
        await credential.close()
