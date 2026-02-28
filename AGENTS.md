# AGENTS.md — Department Agents

**Finance, Sales, Marketing, Support, and Management agents with department-specific workflows.**

---

## Overview

```
/server/agents
├── base_agent.py               # Abstract base class
├── finance_agent.py            # Financial statements, reports, budgets
├── sales_agent.py              # Lead gen, CRM, pitch decks, outreach
├── marketing_agent.py          # Content, playbooks, campaigns
├── support_agent.py            # Ticket analysis, knowledge base, escalation
└── management_agent.py         # Cross-department dashboards, KPIs, audit
```

Each agent is selected by the Router based on the user's department and message intent. Agents load skills on demand, orchestrate multi-tool workflows, and return structured results.

---

## Base Agent (`base_agent.py`)

```python
class BaseAgent:
    def __init__(self, config):
        self.config = config
        self.llm = None       # Set by LLM Manager
        self.skills = {}
        self.tools = {}

    def can_handle(self, task: dict) -> bool:
        """Does this agent handle the task?"""
        raise NotImplementedError

    async def execute(self, task: dict) -> dict:
        """Run the multi-step workflow. Return result dict."""
        raise NotImplementedError

    def _load_skill(self, skill_name):
        """Load a skill and register its tools."""
        ...

    def _require_permission(self, task, permission):
        """Check user has required permission. Raise if not."""
        if permission not in task["permissions"]:
            raise PermissionError(f"Requires '{permission}' permission")
```

### Task Sources

Agents can be invoked from three sources. The `task` dict includes a `source` field:

| Source | Trigger | Auth | Delivery |
|--------|---------|------|----------|
| `mobile` | User sends message via app | JWT + RBAC | Response to app via REST/WebSocket |
| `scheduler` | Celery Beat fires cron job | System-level (no user JWT) | MS Teams channel + Outlook email |
| `webhook` | External event hits `/webhooks/*` | HMAC signature | MS Teams channel + push notification |

For scheduled and webhook tasks, agents deliver results via MS Teams (`teams_post_message`) and/or Outlook email (`outlook_send_email`) instead of returning to the mobile app.
```

---

## Finance Agent (`finance_agent.py`)

**Department:** Finance
**Triggers:** financial statement, P&L, balance sheet, invoice, expense, budget, revenue, report

### Capabilities

- Generate financial statements (P&L, balance sheet, cash flow) from database
- Create expense reports and budget summaries as PDF
- Generate invoices
- Email financial documents to specified recipients (CEO, CFO, auditors)
- Quarterly/monthly financial summaries

### Workflow: "Generate financial statement and send to CEO"

```
1. _load_skill("financial_reporting")
2. database_query → fetch latest financial data (revenue, expenses, assets, liabilities)
3. LLM → analyze and format into statement structure
4. pdf_generator → create branded financial statement PDF
5. Permission check: user has "email_send" permission
6. outlook_send_email → send PDF to CEO via Outlook
7. artifact_store → save PDF to /data/documents
8. Return: summary text + downloadable PDF link
```

### Scheduled Workflow: Monthly Financial Summary (auto, via Celery Beat)

```
Celery Beat fires "monthly-financial-summary" (1st of month, 8AM SGT)
1. _load_skill("financial_reporting")
2. database_query → fetch last month's financial data
3. LLM → generate executive summary with key ratios
4. pdf_generator → create branded monthly report PDF
5. teams_post_message → post PDF to #finance Teams channel
6. outlook_send_email → email PDF to CFO
7. Audit log: source="scheduler", action="monthly_financial_summary"
```

### Required Permissions

| Permission | Actions |
|-----------|---------|
| `finance_read` | Query financial database |
| `finance_write` | Create/update financial records |
| `email_send` | Send emails with financial documents |

### Skills Used

- `financial_reporting` — data formatting, statement generation, ratio calculations

---

## Sales Agent (`sales_agent.py`)

**Department:** Sales
**Triggers:** lead, prospect, LinkedIn, pitch, deck, CRM, outreach, customer, pipeline, deal

### Capabilities

- Search LinkedIn for potential leads by industry, location, company size
- Scrape company websites for contact info and business details
- Generate prospect lists and save to CRM/sales lead database
- Auto-compose and send professional intro emails
- Generate sales pitch decks using Mezzofy product data + customer research
- Track and update sales pipeline

### Workflow: "Find F&B leads in Singapore on LinkedIn and send intro emails"

```
1. _load_skill("linkedin_prospecting")
2. _load_skill("email_outreach")
3. linkedin_scraper → search "F&B companies Singapore" → extract profiles
4. web_scraper → visit company websites for additional context
5. crm_save → store leads in sales_leads table (name, company, email, source, status)
6. LLM → compose personalized intro email per lead using Mezzofy template
7. Permission check: user has "email_send" permission
8. email_send → send emails (with rate limiting to avoid spam flags)
9. crm_update → mark leads as "contacted"
10. csv_export → generate leads CSV for reference
11. Return: summary + CSV artifact
```

### Workflow: "Create a pitch deck for ABC Restaurant Group"

```
1. _load_skill("pitch_deck_generation")
2. mezzofy_data → fetch latest product info, pricing, features, case studies
3. web_research → research ABC Restaurant Group (size, locations, current loyalty program)
4. crm_query → check if ABC is already in CRM, get past interactions
5. LLM → generate slide content (problem, solution, Mezzofy benefits, pricing, case studies)
6. pptx_generator → create branded PPTX from Mezzofy template
7. artifact_store → save deck
8. Return: summary + PPTX download link
```

### Webhook Workflow: New Customer Sign-Up (auto, via webhook)

```
Mezzofy product → POST /webhooks/mezzofy (event: "customer_signed_up")
1. Webhook handler → Celery task → Sales Agent
2. crm_save → add customer to sales_leads (status: "new", source: "product")
3. LLM → compose personalized welcome email
4. outlook_send_email → send welcome email via Outlook
5. teams_post_message → notify #sales: "🎉 New customer: ABC Corp (Enterprise plan)"
6. outlook_create_event → schedule follow-up call in 3 days
7. Audit log: source="webhook", action="customer_onboarding"
```

### Scheduled Workflow: Daily Lead Follow-Up (auto, via Celery Beat)

```
Celery Beat fires "daily-lead-followup" (weekdays 10AM SGT)
1. crm_query → get_stale_leads (follow_up_date ≤ today)
2. For each lead:
   a. LLM → compose follow-up email based on lead context/notes
   b. outlook_send_email → send follow-up via Outlook
   c. crm_update → update last_contacted date
3. teams_post_message → notify assigned sales rep in Teams
4. Audit log: source="scheduler", action="daily_lead_followup"
```

### Required Permissions

| Permission | Actions |
|-----------|---------|
| `sales_read` | Query CRM, view leads |
| `sales_write` | Add/update leads in CRM |
| `email_send` | Send outreach emails |
| `linkedin_access` | Use LinkedIn scraping tools |

### Skills Used

- `linkedin_prospecting` — LinkedIn search, profile extraction, company research
- `email_outreach` — Email template composition, personalization, batch sending
- `pitch_deck_generation` — Slide content generation, PPTX creation
- `web_research` — Company website analysis, competitive research

---

## Marketing Agent (`marketing_agent.py`)

**Department:** Marketing
**Triggers:** content, website, blog, playbook, campaign, social media, newsletter, copy, brand

### Capabilities

- Generate website content (landing pages, feature descriptions, blog posts)
- Create customer-facing playbooks and one-pagers as PDF
- Draft social media posts and email newsletter content
- Generate campaign briefs and marketing plans
- Produce content using Mezzofy brand voice and guidelines

### Workflow: "Write website content and playbook for our new loyalty feature"

```
1. _load_skill("content_generation")
2. mezzofy_data → fetch loyalty feature specs, benefits, pricing
3. knowledge_base → load brand guidelines and tone-of-voice docs
4. LLM → generate website copy (hero text, feature bullets, CTAs)
5. LLM → generate customer playbook (overview, setup guide, best practices, FAQ)
6. document_generator → save website copy as .md
7. pdf_generator → create branded playbook PDF
8. Return: summary + .md and .pdf artifacts
```

### Required Permissions

| Permission | Actions |
|-----------|---------|
| `marketing_read` | Access product data and brand assets |
| `marketing_write` | Create marketing content and campaigns |
| `email_send` | Send content to customers / distribution lists |

### Skills Used

- `content_generation` — Copy writing, playbook creation, social media drafting

---

## Support Agent (`support_agent.py`)

**Department:** Support
**Triggers:** ticket, issue, bug, complaint, customer problem, escalate, SLA, resolution

### Capabilities

- Summarize support tickets (weekly, by category, by severity)
- Flag recurring issues and patterns
- Draft customer response emails
- Search knowledge base for solutions
- Escalation recommendations

### Workflow: "Summarize this week's support tickets and flag recurring issues"

```
1. _load_skill("data_analysis")
2. database_query → fetch all tickets from past 7 days
3. LLM → categorize tickets, identify patterns, calculate resolution times
4. LLM → generate summary with top recurring issues + recommended actions
5. pdf_generator → create weekly support report
6. Return: summary text + PDF report
```

### Scheduled Workflow: Weekly Support Summary (auto, via Celery Beat)

```
Celery Beat fires "weekly-support-summary" (Friday 5PM SGT)
1. _load_skill("data_analysis")
2. database_query → fetch all tickets from past 7 days
3. LLM → categorize, identify patterns, calculate SLA compliance
4. pdf_generator → create weekly support report PDF
5. teams_post_message → post PDF to #support Teams channel
6. outlook_send_email → email PDF to support manager
7. Audit log: source="scheduler", action="weekly_support_summary"
```

### Webhook Workflow: New Support Ticket (auto, via webhook)

```
Mezzofy product → POST /webhooks/mezzofy (event: "support_ticket_created")
1. Webhook handler → Celery task → Support Agent
2. LLM → classify ticket severity and category
3. knowledge_base → search for known solutions
4. teams_post_message → alert #support: "🎫 New ticket: [category] — [subject]"
5. If high severity → outlook_send_email → escalate to support manager
6. Audit log: source="webhook", action="ticket_triage"
```

### Required Permissions

| Permission | Actions |
|-----------|---------|
| `support_read` | Query ticket database |
| `support_write` | Update tickets, add notes |
| `email_send` | Send responses to customers |

---

## Management Agent (`management_agent.py`)

**Department:** Management
**Triggers:** KPI, dashboard, report, overview, performance, team, cross-department, audit, cost

### Capabilities

- Cross-department KPI dashboards (sales pipeline, support resolution, marketing reach)
- LLM usage cost reports
- Team activity summaries
- Audit log review
- Financial overview with operational context

### Workflow: "Give me a KPI dashboard across all departments this month"

```
1. _load_skill("data_analysis")
2. database_query → sales: pipeline value, leads generated, deals closed
3. database_query → support: tickets opened, resolved, avg resolution time, SLA %
4. database_query → marketing: content pieces created, campaigns launched
5. database_query → finance: revenue, expenses, key ratios
6. database_query → llm_usage: tokens consumed, cost by department
7. LLM → synthesize into executive summary with highlights and concerns
8. pdf_generator → create KPI report
9. Return: summary + PDF report
```

### Scheduled Workflow: Weekly KPI Report (auto, via Celery Beat)

```
Celery Beat fires "weekly-kpi-report" (Monday 9AM SGT)
1. _load_skill("data_analysis")
2. database_query → all department metrics for past week
3. LLM → synthesize executive summary
4. pdf_generator → create branded KPI report PDF
5. teams_post_message → post PDF to #management Teams channel
6. outlook_send_email → email PDF to CEO and COO
7. Audit log: source="scheduler", action="weekly_kpi_report"
```

### Required Permissions

| Permission | Actions |
|-----------|---------|
| `management_read` | Query all department databases |
| `management_admin` | User management, role assignment |
| `audit_read` | View audit logs |

---

## Agent Selection by Router

```python
AGENT_MAP = {
    "finance": FinanceAgent,
    "sales": SalesAgent,
    "marketing": MarketingAgent,
    "support": SupportAgent,
    "management": ManagementAgent,
}

# Router logic (mobile requests):
# 1. User's department provides a strong hint
# 2. LLM classification confirms or overrides
# 3. Management users can trigger any department's agent
# 4. Cross-department requests → Management Agent

# Scheduler routing:
# Celery Beat jobs specify agent directly in beat_schedule.py
# e.g. {"agent": "finance", "message": "Generate monthly summary"}

# Webhook routing:
# Webhook events map to agents via WEBHOOK_AGENT_MAP
# e.g. "customer_signed_up" → Sales Agent
#      "support_ticket_created" → Support Agent
```

---

## Adding a New Department Agent

1. Create `/server/agents/new_dept_agent.py` inheriting from `BaseAgent`
2. Implement `can_handle()` with department-specific keywords
3. Implement `execute()` with skill loading and tool orchestration
4. Add to `AGENT_MAP` in router
5. Define permissions in `/config/roles.yaml`
6. Create required skills in `/skills/available/`
