"""
SalesAgent — Lead generation, CRM, pitch decks, and outreach.

Handles: LinkedIn prospecting, company research, CRM management,
personalized email outreach, pitch deck generation, and pipeline tracking.

Sources:
  - mobile: User request from Sales department
  - scheduler: Daily lead follow-up (weekdays 10AM SGT)
  - webhook: New customer sign-up from Mezzofy product
"""

import logging

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.sales")

_TRIGGER_KEYWORDS = {
    "lead", "prospect", "linkedin", "pitch", "deck", "crm", "outreach",
    "customer", "pipeline", "deal", "contact", "company", "intro email",
    "follow up", "followup", "sales", "opportunity", "convert", "demo",
}


class SalesAgent(BaseAgent):
    """
    Orchestrates LinkedIn prospecting, CRM operations, and pitch deck creation.

    Key workflows:
    - LinkedIn search → extract profiles → save to CRM → compose + send intro emails
    - Create pitch deck for specific customer using Mezzofy product data
    - Daily automated follow-up for stale CRM leads
    - New customer onboarding via webhook
    """

    def can_handle(self, task: dict) -> bool:
        department = task.get("department", "").lower()
        if department == "sales":
            return True
        message = task.get("message", "").lower()
        return any(kw in message for kw in _TRIGGER_KEYWORDS)

    async def execute(self, task: dict) -> dict:
        source = task.get("source", "mobile")
        message = task.get("message", "").lower()

        # Route to appropriate sub-workflow
        if source == "scheduler" and "follow" in message:
            return await self._daily_followup_workflow(task)
        if source == "webhook" and "customer_signed_up" in task.get("event", ""):
            return await self._customer_onboarding_workflow(task)
        if any(w in message for w in ("pitch deck", "pitch", "deck", "presentation")):
            return await self._pitch_deck_workflow(task)
        if any(w in message for w in ("linkedin", "prospect", "lead", "find")):
            return await self._prospecting_workflow(task)
        return await self._general_sales_workflow(task)

    # ── Sub-workflows ─────────────────────────────────────────────────────────

    async def _prospecting_workflow(self, task: dict) -> dict:
        """LinkedIn search → CRM save → compose + send intro emails."""
        try:
            li_skill = self._load_skill("linkedin_prospecting")
            email_skill = self._load_skill("email_outreach")
        except ValueError as e:
            return self._err(str(e))

        message = task.get("message", "")
        tools_called = []

        # Step 1: LinkedIn search
        li_result = await li_skill.search_linkedin(
            query=message,
            search_type="company",
            max_results=10,
        )
        tools_called.append("linkedin_search")
        if not li_result.get("success"):
            return self._err(f"LinkedIn search failed: {li_result.get('error')}")

        leads = li_result.get("output", [])
        if not isinstance(leads, list):
            leads = [leads]

        # Step 2: Save to CRM
        from app.tools.database.crm_ops import CRMOps
        crm = CRMOps(self.config)
        saved_count = 0
        for lead in leads[:10]:
            crm_result = await crm.execute(
                "create_lead",
                name=str(lead.get("name", "Unknown")),
                company=str(lead.get("company", "")),
                email=str(lead.get("email", "")),
                source="linkedin",
                status="new",
                notes=str(lead.get("description", ""))[:500],
            )
            if crm_result.get("success"):
                saved_count += 1
        tools_called.append("create_lead")

        # Step 3: Compose and send intro emails
        self._require_permission(task, "email_send")
        sent_count = 0
        for lead in leads[:5]:  # Limit initial outreach
            email_result = lead.get("email", "")
            if not email_result:
                continue
            compose_result = await email_skill.compose_email(
                template="intro",
                recipient_name=str(lead.get("name", "there")),
                recipient_email=str(email_result),
                company_name=str(lead.get("company", "")),
            )
            if compose_result.get("success"):
                composed = compose_result["output"]
                send_result = await email_skill.send_email(
                    to=str(email_result),
                    subject=composed["subject"],
                    body_html=composed["body_html"],
                )
                if send_result.get("success"):
                    sent_count += 1
        tools_called.extend(["compose_email", "send_email"])

        summary = (
            f"LinkedIn prospecting complete:\n"
            f"- Found {len(leads)} leads\n"
            f"- Saved {saved_count} to CRM\n"
            f"- Sent {sent_count} intro emails"
        )
        return self._ok(content=summary, tools_called=tools_called)

    async def _pitch_deck_workflow(self, task: dict) -> dict:
        """Generate a pitch deck for a specific customer."""
        try:
            deck_skill = self._load_skill("pitch_deck_generation")
            research_skill = self._load_skill("web_research")
        except ValueError as e:
            return self._err(str(e))

        user_input = task.get("extracted_text") or task.get("message", "")
        tools_called = []

        # Extract customer name from message using LLM
        extract_result = await llm_mod.get().chat(
            messages=[{
                "role": "user",
                "content": (
                    f"Extract the company/customer name from this message. "
                    f"Return ONLY the name, nothing else.\n\nMessage: {user_input}"
                ),
            }],
            task_context=task,
        )
        customer_name = extract_result.get("content", "Customer").strip()

        # Research the company
        research_result = await research_skill.search_web(query=f"{customer_name} company")
        tools_called.append("search_web")

        # Create pitch deck
        deck_result = await deck_skill.create_pitch_deck(
            customer_name=customer_name,
            include_pricing=True,
            include_case_studies=True,
        )
        tools_called.append("create_pitch_deck")

        if not deck_result.get("success"):
            return self._err(f"Pitch deck creation failed: {deck_result.get('error')}")

        artifacts = [{
            "name": f"pitch_deck_{customer_name.replace(' ', '_')}.pptx",
            "path": deck_result.get("output", ""),
            "type": "pptx",
        }]
        return self._ok(
            content=f"Pitch deck created for {customer_name}. Ready to download.",
            artifacts=artifacts,
            tools_called=tools_called,
        )

    async def _daily_followup_workflow(self, task: dict) -> dict:
        """Automated: follow up on stale CRM leads (scheduler)."""
        from app.tools.database.crm_ops import CRMOps
        crm = CRMOps(self.config)
        tools_called = []

        stale_result = await crm.execute("get_stale_leads", days_overdue=1)
        tools_called.append("get_stale_leads")
        if not stale_result.get("success"):
            return self._err(f"CRM query failed: {stale_result.get('error')}")

        leads = stale_result.get("output", [])
        if not isinstance(leads, list):
            leads = []

        try:
            email_skill = self._load_skill("email_outreach")
        except ValueError as e:
            return self._err(str(e))

        sent = 0
        for lead in leads[:20]:
            email = lead.get("email", "")
            if not email:
                continue
            compose = await email_skill.compose_email(
                template="followup",
                recipient_name=str(lead.get("name", "there")),
                recipient_email=str(email),
                company_name=str(lead.get("company", "")),
            )
            if compose.get("success"):
                c = compose["output"]
                send = await email_skill.send_email(
                    to=str(email),
                    subject=c["subject"],
                    body_html=c["body_html"],
                )
                if send.get("success"):
                    sent += 1
                    await crm.execute("update_lead", lead_id=lead.get("id"), status="contacted")
        tools_called.extend(["compose_email", "send_email", "update_lead"])

        summary = f"Daily follow-up: sent {sent} emails to {len(leads)} stale leads."
        await self._deliver_to_teams(channel="#sales", message=f"📧 {summary}")
        return self._ok(content=summary, tools_called=tools_called)

    async def _customer_onboarding_workflow(self, task: dict) -> dict:
        """Webhook: new customer signed up in Mezzofy product."""
        payload = task.get("payload", {})
        customer_name = payload.get("company_name", "New Customer")
        customer_email = payload.get("contact_email", "")
        plan = payload.get("plan", "Standard")
        tools_called = []

        # Save to CRM
        from app.tools.database.crm_ops import CRMOps
        crm = CRMOps(self.config)
        await crm.execute(
            "create_lead",
            name=payload.get("contact_name", customer_name),
            company=customer_name,
            email=customer_email,
            source="product",
            status="new",
        )
        tools_called.append("create_lead")

        # Send welcome email
        if customer_email:
            try:
                email_skill = self._load_skill("email_outreach")
                compose = await email_skill.compose_email(
                    template="intro",
                    recipient_name=payload.get("contact_name", "there"),
                    recipient_email=customer_email,
                    company_name=customer_name,
                    custom_context=f"Welcome to Mezzofy! You're now on the {plan} plan.",
                )
                if compose.get("success"):
                    c = compose["output"]
                    await email_skill.send_email(
                        to=customer_email,
                        subject=f"Welcome to Mezzofy, {customer_name}!",
                        body_html=c["body_html"],
                    )
                tools_called.extend(["compose_email", "send_email"])
            except ValueError:
                pass

        # Notify Teams
        await self._deliver_to_teams(
            channel="#sales",
            message=f"🎉 New customer: {customer_name} ({plan} plan)",
        )

        return self._ok(
            content=f"Onboarding complete for {customer_name} ({plan} plan).",
            tools_called=tools_called,
        )

    async def _general_sales_workflow(self, task: dict) -> dict:
        """Fallback: route to LLM with sales context and all tools."""
        llm = llm_mod.get()
        result = await llm.execute_with_tools(task)
        return self._ok(
            content=result.get("content", ""),
            tools_called=result.get("tools_called", []),
        )
