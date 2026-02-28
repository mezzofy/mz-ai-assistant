# SKILLS.md — Modular Skill System

**Business-focused skills for LinkedIn prospecting, financial reporting, pitch decks, content generation, and email outreach.**

---

## Overview

```
/server/skills
├── skill_loader.py             # Dynamic YAML + Python loading
├── skill_registry.py           # Central registration
└── /available                  # Skill packages (YAML def + Python impl)
    ├── linkedin_prospecting.yaml + .py
    ├── financial_reporting.yaml + .py
    ├── pitch_deck_generation.yaml + .py
    ├── email_outreach.yaml + .py
    ├── content_generation.yaml + .py
    ├── web_research.yaml + .py
    └── data_analysis.yaml + .py
```

Each skill is a paired YAML definition + Python implementation. YAML declares metadata, dependencies, and tool schemas. Python provides the logic.

---

## Skill Definitions

### 1. LinkedIn Prospecting

**Agent:** Sales

```yaml
# linkedin_prospecting.yaml
name: "linkedin_prospecting"
version: "1.0.0"
description: "Search LinkedIn for leads, extract profiles, and research companies"
agent: "sales"

dependencies:
  - playwright>=1.40.0
  - beautifulsoup4>=4.12.0

capabilities:
  - search_linkedin_companies
  - search_linkedin_people
  - extract_company_info
  - extract_contact_info

tools:
  - name: "linkedin_search"
    description: "Search LinkedIn for companies or people by industry, location, size"
    parameters:
      query: { type: "string", required: true }
      search_type: { type: "string", required: true }   # "company" or "people"
      location: { type: "string", required: false }
      industry: { type: "string", required: false }
      max_results: { type: "integer", required: false }

  - name: "linkedin_extract_profile"
    description: "Extract details from a LinkedIn company or person profile URL"
    parameters:
      url: { type: "string", required: true }
```

**Implementation highlights:**
- Uses Playwright for headless LinkedIn access
- Respects rate limits to avoid account blocks
- Extracts: company name, industry, size, location, website, key contacts
- Returns structured data for CRM insertion

---

### 2. Financial Reporting

**Agent:** Finance

```yaml
# financial_reporting.yaml
name: "financial_reporting"
version: "1.0.0"
description: "Generate financial statements, reports, and analyses from database"
agent: "finance"

dependencies:
  - reportlab>=4.0.0
  - pandas>=2.0.0

capabilities:
  - generate_pnl_statement
  - generate_balance_sheet
  - generate_cash_flow
  - generate_expense_report
  - calculate_financial_ratios

tools:
  - name: "financial_query"
    description: "Query financial data by date range, category, and type"
    parameters:
      report_type: { type: "string", required: true }   # pnl, balance_sheet, cash_flow
      start_date: { type: "string", required: true }
      end_date: { type: "string", required: true }
      department: { type: "string", required: false }

  - name: "financial_format"
    description: "Format financial data into a professional statement structure"
    parameters:
      data: { type: "object", required: true }
      format: { type: "string", required: true }         # pdf, csv, json
```

---

### 3. Pitch Deck Generation

**Agent:** Sales

```yaml
# pitch_deck_generation.yaml
name: "pitch_deck_generation"
version: "1.0.0"
description: "Create sales pitch decks using Mezzofy product data and customer research"
agent: "sales"

dependencies:
  - python-pptx>=0.6.21

capabilities:
  - generate_pitch_deck
  - customize_template
  - insert_case_studies
  - add_pricing_slide

tools:
  - name: "create_pitch_deck"
    description: "Generate PPTX pitch deck for a specific customer/prospect"
    parameters:
      customer_name: { type: "string", required: true }
      industry: { type: "string", required: false }
      focus_products: { type: "array", required: false }
      include_pricing: { type: "boolean", required: false }
      include_case_studies: { type: "boolean", required: false }

  - name: "get_mezzofy_products"
    description: "Fetch latest Mezzofy product data, features, and pricing"
    parameters:
      product_category: { type: "string", required: false }
```

**Implementation highlights:**
- Loads Mezzofy PPTX template from `/knowledge/templates/`
- Dynamically inserts customer name, industry context, relevant case studies
- Pulls latest product data from knowledge base
- Creates slides: Cover, Problem, Solution, Product Features, Case Studies, Pricing, CTA

---

### 4. Email Outreach

**Agent:** Sales, Marketing, Support

```yaml
# email_outreach.yaml
name: "email_outreach"
version: "1.0.0"
description: "Compose and send professional emails via Outlook (MS Graph) with templates and personalization"
agent: "sales"

dependencies:
  - msgraph-sdk>=1.2.0
  - jinja2>=3.1.0

capabilities:
  - compose_intro_email
  - compose_followup_email
  - compose_proposal_email
  - batch_send

tools:
  - name: "compose_email"
    description: "Draft a professional email from template with personalization"
    parameters:
      template: { type: "string", required: true }     # intro, followup, proposal, custom
      recipient_name: { type: "string", required: true }
      recipient_email: { type: "string", required: true }
      company_name: { type: "string", required: false }
      custom_context: { type: "string", required: false }

  - name: "send_email"
    description: "Send composed email via Outlook (MS Graph API)"
    parameters:
      to: { type: "string", required: true }
      subject: { type: "string", required: true }
      body_html: { type: "string", required: true }
      cc: { type: "array", required: false }
      attachments: { type: "array", required: false }
```

**Implementation highlights:**
- Email templates stored in `/knowledge/templates/emails/`
- LLM personalizes each email based on recipient context
- Sends via Microsoft Graph API (Outlook), not raw SMTP
- Rate-limited batch sending (max 30/hour to avoid Microsoft throttling)
- All sent emails logged in database for audit trail
- Supports scheduled auto-send for follow-up workflows

---

### 5. Content Generation

**Agent:** Marketing

```yaml
# content_generation.yaml
name: "content_generation"
version: "1.0.0"
description: "Generate marketing content — website copy, playbooks, blogs, social media"
agent: "marketing"

capabilities:
  - generate_website_copy
  - generate_playbook
  - generate_blog_post
  - generate_social_posts
  - generate_newsletter

tools:
  - name: "generate_content"
    description: "Create marketing content of specified type"
    parameters:
      content_type: { type: "string", required: true }  # website, playbook, blog, social, newsletter
      topic: { type: "string", required: true }
      audience: { type: "string", required: false }      # prospects, customers, partners
      tone: { type: "string", required: false }          # professional, casual, technical
      length: { type: "string", required: false }        # short, medium, long
```

**Implementation highlights:**
- Loads Mezzofy brand guidelines from `/knowledge/brand/`
- Pulls product data from knowledge base for accuracy
- Generates content in Mezzofy brand voice
- Outputs as Markdown (website), PDF (playbook), or plain text (social)

---

### 6. Web Research

**Agent:** Sales, Marketing, Management

```yaml
# web_research.yaml
name: "web_research"
version: "1.0.0"
description: "Research companies, competitors, and markets via web scraping"
agent: "sales"

dependencies:
  - playwright>=1.40.0
  - beautifulsoup4>=4.12.0

tools:
  - name: "research_company"
    description: "Research a company by scraping their website and public data"
    parameters:
      company_name: { type: "string", required: true }
      website_url: { type: "string", required: false }
      focus_areas: { type: "array", required: false }   # products, team, funding, news

  - name: "search_web"
    description: "General web search and extract relevant information"
    parameters:
      query: { type: "string", required: true }
      max_results: { type: "integer", required: false }
```

---

### 7. Data Analysis

**Agent:** Support, Management, Finance

```yaml
# data_analysis.yaml
name: "data_analysis"
version: "1.0.0"
description: "Analyze datasets, generate summaries, identify trends and patterns"
agent: "management"

dependencies:
  - pandas>=2.0.0

tools:
  - name: "analyze_data"
    description: "Analyze a dataset and return summary statistics and insights"
    parameters:
      query: { type: "string", required: true }         # SQL or natural language
      analysis_type: { type: "string", required: false } # summary, trend, comparison
      date_range: { type: "string", required: false }
```

---

## Skill Loader

Same pattern as the original spec — scans `/available/` for YAML files, loads matching Python modules, creates tool wrappers:

```python
class SkillLoader:
    def load_all(self):
        for yaml_file in self.skills_dir.glob("*.yaml"):
            skill_def = yaml.safe_load(yaml_file.read_text())
            skill_class = self._load_implementation(skill_def)
            # Register tools...
```

---

## Skill ↔ Agent Mapping

| Skill | Finance | Sales | Marketing | Support | Management |
|-------|---------|-------|-----------|---------|------------|
| linkedin_prospecting | | ✅ | | | |
| financial_reporting | ✅ | | | | ✅ |
| pitch_deck_generation | | ✅ | | | |
| email_outreach | | ✅ | ✅ | ✅ | |
| content_generation | | | ✅ | | |
| web_research | | ✅ | ✅ | | ✅ |
| data_analysis | ✅ | | | ✅ | ✅ |

---

## Adding a New Skill

1. Create `skill_name.yaml` + `skill_name.py` in `/skills/available/`
2. YAML: declare name, agent, dependencies, capabilities, tools
3. Python: class `SkillNameSkill` with one method per tool
4. Install any new pip dependencies
5. Assign to agents in the mapping above
