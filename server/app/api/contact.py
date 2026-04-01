"""
Public Contact Form Endpoint — receives website contact form submissions and
forwards them to hello@mezzofy.com via MS Graph (same infrastructure as auth emails).

Route:  POST /contact
Auth:   None (public — bypasses ChatGatewayMiddleware)
CORS:   Handled by CORSMiddleware in main.py

Rate limiting is kept simple (no Redis required): a honeypot field `_gotcha`
must be empty (filled only by bots), and all required fields are validated
server-side so bad payloads are rejected without hitting MS Graph.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.core.email_sender import send_transactional_email

logger = logging.getLogger("mezzofy.api.contact")

router = APIRouter(tags=["contact"])

_RECIPIENT = "hello@mezzofy.com"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ── Request schema ─────────────────────────────────────────────────────────────

class ContactFormPayload(BaseModel):
    model_config = {"populate_by_name": True}

    name: str
    email: str
    company: Optional[str] = ""
    phone: Optional[str] = ""
    subject: str
    message: str
    gotcha: Optional[str] = Field(default="", alias="_gotcha")  # honeypot — must be empty

    @field_validator("name", "subject", "message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field is required and cannot be blank")
        return v.strip()

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("company", "phone", mode="before")
    @classmethod
    def optional_strip(cls, v) -> str:
        return (v or "").strip()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_email_html(p: ContactFormPayload) -> str:
    """Render a clean HTML email body for the hello@mezzofy.com inbox."""
    def row(label: str, value: str) -> str:
        if not value:
            return ""
        return (
            f'<tr>'
            f'<td style="padding:8px 12px;background:#f5f5f5;font-weight:600;'
            f'color:#1a1a1a;width:140px;vertical-align:top;">{label}</td>'
            f'<td style="padding:8px 12px;color:#424242;">{value}</td>'
            f'</tr>'
        )

    rows = "".join([
        row("Name",    p.name),
        row("Email",   f'<a href="mailto:{p.email}" style="color:#FF6B35;">{p.email}</a>'),
        row("Company", p.company or ""),
        row("Phone",   p.phone or ""),
        row("Subject", p.subject),
    ])

    message_html = p.message.replace("\n", "<br>")

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#1a1a1a;padding:24px 32px;">
            <span style="color:#FF6B35;font-size:22px;font-weight:700;
                         letter-spacing:1px;">MEZZOFY</span>
            <span style="color:#ffffff;font-size:14px;margin-left:12px;">
              New Contact Form Submission
            </span>
          </td>
        </tr>

        <!-- Contact details table -->
        <tr>
          <td style="padding:24px 32px 8px;">
            <table width="100%" cellpadding="0" cellspacing="4"
                   style="border-collapse:separate;border-spacing:0 4px;">
              {rows}
            </table>
          </td>
        </tr>

        <!-- Message -->
        <tr>
          <td style="padding:8px 32px 32px;">
            <p style="margin:0 0 8px;font-weight:600;color:#1a1a1a;">Message</p>
            <div style="background:#f5f5f5;border-left:3px solid #FF6B35;
                        padding:16px;border-radius:4px;color:#424242;
                        line-height:1.6;">
              {message_html}
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f5f5f5;padding:16px 32px;
                     border-top:1px solid #e0e0e0;">
            <p style="margin:0;font-size:12px;color:#757575;">
              Sent from the Mezzofy website contact form &mdash;
              <a href="https://mezzofy.com/contact.html"
                 style="color:#FF6B35;text-decoration:none;">mezzofy.com/contact.html</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/contact")
async def submit_contact_form(payload: ContactFormPayload, request: Request):
    """
    Receive a contact form submission and forward it to hello@mezzofy.com.

    Returns: {"ok": true} on success, raises HTTP 422/500 on failure.
    Bot protection: honeypot field `_gotcha` must be absent or empty.
    """
    # Honeypot check — bots typically fill all fields
    if (payload.gotcha or "").strip():
        # Silently accept (don't reveal detection) but do nothing
        logger.info(f"Honeypot triggered from {request.client.host if request.client else 'unknown'}")
        return {"ok": True}

    subject = f"[Mezzofy Website] {payload.subject} — from {payload.name}"
    body_html = _build_email_html(payload)

    try:
        await send_transactional_email(
            to=_RECIPIENT,
            subject=subject,
            body_html=body_html,
        )
        logger.info(
            f"Contact form forwarded to {_RECIPIENT} — "
            f"from={payload.email}, subject={payload.subject!r}"
        )
    except RuntimeError as exc:
        logger.error(f"Contact form send failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to send email. Please try again later.")

    return {"ok": True}
