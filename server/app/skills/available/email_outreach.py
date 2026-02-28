"""
EmailOutreachSkill — Professional email composition and sending via Outlook.

Uses Jinja2 for template rendering and OutlookOps (MS Graph) for delivery.
Rate-limited to avoid Microsoft throttling (max 30/hour).
Used by SalesAgent, MarketingAgent, and SupportAgent.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.skills.email_outreach")

# Built-in email templates (used when no file-based template found)
_BUILTIN_TEMPLATES: dict[str, str] = {
    "intro": """
<p>Dear {{ recipient_name }},</p>

<p>My name is [Sender Name] from Mezzofy. I came across {{ company_name or 'your company' }}
and believe our coupon and loyalty platform could be a great fit for your business.</p>

<p>Mezzofy helps merchants like you increase customer retention and drive repeat purchases
through a fully managed loyalty exchange platform. Our clients typically see a
<strong>20–35% uplift</strong> in customer lifetime value within the first 3 months.</p>

<p>I'd love to share a quick demo at your convenience. Would you have 20 minutes this week?</p>

<p>Best regards,<br>The Mezzofy Sales Team</p>
{{ custom_context or '' }}
""",
    "followup": """
<p>Dear {{ recipient_name }},</p>

<p>I wanted to follow up on my previous message about Mezzofy's loyalty platform.</p>

<p>I understand you're busy, but I'd love to show you how we've helped businesses
similar to {{ company_name or 'yours' }} increase customer loyalty and reduce churn.</p>

<p>Would this week work for a brief 15-minute call?</p>

<p>Best regards,<br>The Mezzofy Sales Team</p>
{{ custom_context or '' }}
""",
    "proposal": """
<p>Dear {{ recipient_name }},</p>

<p>Thank you for your time. As discussed, please find our proposal attached.</p>

<p>The proposal outlines how Mezzofy can help {{ company_name or 'your business' }}
achieve your loyalty and retention goals. Key highlights:</p>
<ul>
  <li>Quick 2-week onboarding</li>
  <li>Dedicated customer success manager</li>
  <li>ROI positive within 60 days</li>
</ul>

<p>I'm available to answer any questions at your convenience.</p>

<p>Best regards,<br>The Mezzofy Sales Team</p>
{{ custom_context or '' }}
""",
}


class EmailOutreachSkill:
    """
    Composes and sends professional emails via Outlook (MS Graph).

    Templates are loaded from knowledge base first; falls back to built-in
    templates if not found. Rate-limited to 30/hour for batch sends.
    """

    def __init__(self, config: dict):
        self.config = config
        from app.tools.communication.outlook_ops import OutlookOps
        self._outlook = OutlookOps(config)
        self._sent_count = 0
        self._hour_reset_ts: float = 0.0

    # ── Public methods ────────────────────────────────────────────────────────

    async def compose_email(
        self,
        template: str,
        recipient_name: str,
        recipient_email: str,
        company_name: Optional[str] = None,
        custom_context: Optional[str] = None,
    ) -> dict:
        """
        Draft a personalized email from a named template.

        Args:
            template: "intro", "followup", "proposal", or "custom".
            recipient_name: Recipient's full name.
            recipient_email: Recipient's email address.
            company_name: Recipient's company (used in template).
            custom_context: Extra personalization text injected into template.

        Returns:
            {success: bool, output: {subject: str, body_html: str} | error: str}
        """
        try:
            from jinja2 import Template

            template_str = self._load_template(template)
            rendered = Template(template_str).render(
                recipient_name=recipient_name,
                company_name=company_name or "",
                custom_context=custom_context or "",
            )

            subject_map = {
                "intro": f"Introducing Mezzofy — Loyalty Platform for {company_name or 'Your Business'}",
                "followup": "Following Up — Mezzofy Loyalty Platform",
                "proposal": f"Mezzofy Proposal for {company_name or recipient_name}",
                "custom": f"Message for {recipient_name}",
            }
            subject = subject_map.get(template, f"Message for {recipient_name}")

            logger.info(
                f"EmailOutreachSkill.compose_email: template={template} "
                f"to={recipient_email}"
            )
            return {"success": True, "output": {"subject": subject, "body_html": rendered}}

        except Exception as e:
            logger.error(f"EmailOutreachSkill.compose_email failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
        cc: Optional[list] = None,
        attachments: Optional[list] = None,
    ) -> dict:
        """
        Send an email via Outlook (MS Graph API).

        Rate-limited to 30 emails/hour to avoid Microsoft throttling.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body_html: HTML body content.
            cc: Optional list of CC email addresses.
            attachments: Optional list of file paths to attach.

        Returns:
            {success: bool, output: str | error: str}
        """
        try:
            if not await self._check_rate_limit():
                return {
                    "success": False,
                    "error": "Email rate limit reached (30/hour). Please try again later.",
                }

            result = await self._outlook.execute(
                "outlook_send_email",
                to=to,
                subject=subject,
                body=body_html,
                body_type="HTML",
                cc=cc or [],
                attachments=attachments or [],
            )
            if result.get("success"):
                self._sent_count += 1
                logger.info(f"EmailOutreachSkill.send_email: sent to={to}")
            return result

        except Exception as e:
            logger.error(f"EmailOutreachSkill.send_email failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_template(self, template_name: str) -> str:
        """Load template from knowledge base; fall back to built-in."""
        kb_dir = self.config.get("tools", {}).get("knowledge_base", {}).get("directory", "knowledge")
        template_path = (
            Path(__file__).parent.parent.parent.parent
            / kb_dir
            / "templates"
            / "emails"
            / f"{template_name}.html"
        )
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")

        if template_name in _BUILTIN_TEMPLATES:
            return _BUILTIN_TEMPLATES[template_name]

        return _BUILTIN_TEMPLATES["intro"]

    async def _check_rate_limit(self) -> bool:
        """Return True if under rate limit (30/hour)."""
        import time
        now = time.time()
        if now - self._hour_reset_ts > 3600:
            self._sent_count = 0
            self._hour_reset_ts = now
        return self._sent_count < 30
