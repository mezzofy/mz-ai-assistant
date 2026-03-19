# Mezzofy AI Assistant — User Guide: Agentic Features

**Version:** 2.0.0
**Last Updated:** March 19, 2026
**Audience:** All Mezzofy business users (mobile & web)

---

## Table of Contents

1. [What are Agentic Features?](#what-are-agentic-features)
2. [Your AI Team](#your-ai-team)
3. [How to Talk to the AI](#how-to-talk-to-the-ai)
4. [Triggering Special Agents](#triggering-special-agents)
5. [Cross-Department Requests (Orchestration)](#cross-department-requests-orchestration)
6. [Scheduled Jobs Reference](#scheduled-jobs-reference)
7. [File Storage Guide](#file-storage-guide)
8. [Tips & Tricks](#tips--tricks)

---

## What are Agentic Features?

Most AI assistants simply answer questions. The Mezzofy AI Assistant goes further — it acts.

**A simple chatbot:** You ask "What were our Q1 sales?" and it replies with text.

**An agentic AI assistant:** You ask "Send me a Q1 sales report every Monday morning" and it:
1. Creates a recurring schedule
2. Every Monday, queries your sales database
3. Generates a branded PDF
4. Emails it to you automatically — without you doing anything

The difference is that **agentic AI can take multi-step actions**, remember your preferences, coordinate multiple tasks, and even hand work off to a specialist when needed.

**The Mezzofy AI Assistant has a team of 9 specialists**, each expert in one area of your business. When you send a message, the right expert picks it up automatically.

---

## Your AI Team

You don't need to address agents by name. Just describe what you need — the system routes your request automatically based on your department and the content of your message.

| Agent | Name | Department | What They're Best At |
|-------|------|:----------:|----------------------|
| Management Agent | Max | Management | Company-wide KPI dashboards, executive reports, cross-department insights, LinkedIn prospecting |
| Finance Agent | Fiona | Finance | Financial reports, revenue analysis, expense summaries, CSV exports |
| Sales Agent | Sam | Sales | CRM lead management, sales emails, pitch decks, LinkedIn lead search |
| Marketing Agent | Maya | Marketing | Marketing content, campaign emails, competitive research |
| Support Agent | Suki | Support | Ticket reports, customer emails, SLA performance summaries |
| HR Agent | Hana | HR | Leave management, org charts, HR reports, employee communications |
| Research Agent | Rex | (All depts) | Deep web research, competitive intelligence, market analysis |
| Developer Agent | Dev | (All depts) | Code writing, script generation, API integrations, test writing |
| Scheduler Agent | Sched | (All depts) | Setting up automatic recurring tasks |

---

## How to Talk to the AI

You don't need special syntax. Just write naturally, as you would to a colleague.

### Examples by Department

**Finance:**
> "Give me a revenue summary for February"
> "Export Q4 financial data to CSV"
> "Create a PDF report of this month's expenses"

**Sales:**
> "Find tech startups in Singapore on LinkedIn and add them to CRM"
> "Send intro emails to the leads I added this week"
> "What's the current sales pipeline status?"

**Marketing:**
> "Write a LinkedIn post announcing our new coupon feature"
> "Send our March newsletter to the marketing list"
> "Research what our top 3 competitors are saying on their blogs"

**Support:**
> "How many tickets were opened this week?"
> "Show me all overdue support tickets"
> "Send a follow-up email to the customer who opened ticket #1042"

**HR:**
> "How many people are on leave this week?"
> "Generate the org chart as a PDF"
> "Export leave data for Q1 to CSV"

**Management:**
> "Give me a company-wide KPI dashboard for this month"
> "Compare sales and finance performance this quarter"
> "Find 10 logistics companies on LinkedIn for our expansion"

### Tips for Best Results

- **Be specific about dates:** "last month" works, but "February 2026" is better
- **Specify the output format** if you have a preference: "as a PDF", "as CSV", "as a PowerPoint"
- **Name the delivery channel** if needed: "send to Teams", "email me", "save to my files"
- **One task at a time** gives the best results — complex multi-step requests work best when broken into steps

---

## Triggering Special Agents

Three agents handle specialized work that goes beyond normal department tasks. They activate automatically when your message contains the right keywords.

---

### Research Agent (Rex)

**When it activates:** Your message contains words like: *research, investigate, find out, market analysis, competitor, what is the, how does, study, analyse*. Or start your message with `research:`.

**What it does:**
1. Understands your research question
2. Searches the web across multiple sources (up to 8 search rounds)
3. Cross-checks and verifies sources for credibility
4. Synthesises findings into a structured report with citations

**Expected output:** A detailed written report with key findings, source references, and a summary.

**Sample prompts:**

| What you want | What to type |
|--------------|-------------|
| Competitor research | `"Research our top 5 competitors in Singapore"` |
| Market sizing | `"What is the market size for digital coupons in Southeast Asia?"` |
| News about a topic | `"research: Latest regulatory changes for fintech in Malaysia 2026"` |
| Company background | `"Find background on XYZ Corp — products, funding, key people"` |

**What happens step by step:**
1. You send the message
2. The system assigns it to Rex (Research Agent)
3. The task runs in the background — you'll see live progress updates on your screen
4. Rex searches the web multiple times, refining each search
5. Rex synthesises the findings
6. You receive the completed report (usually within 1–2 minutes)

> **Note:** Research tasks run asynchronously. You can keep using the app while Rex works.

---

### Developer Agent (Dev)

**When it activates:** Your message contains words like: *build, code, script, write a function, create an API, generate a program, develop, automate*. Or start your message with `developer:`.

**What it does:**
1. Understands your technical requirement
2. Writes the code using Claude Code (an advanced coding AI)
3. Shows you step-by-step what it's building
4. Returns the finished code or script

**Expected output:** Working code, a script, or a technical implementation with explanations.

**Sample prompts:**

| What you want | What to type |
|--------------|-------------|
| Data processing script | `"Build a Python script to process our leads CSV and flag duplicates"` |
| API integration | `"developer: Write a script to fetch data from our CRM API and export to CSV"` |
| Automation | `"Create a script that reads our sales data and generates a weekly summary email"` |
| Test writing | `"Write unit tests for our scheduler module"` |

**What happens step by step:**
1. You send the message
2. Dev receives the task
3. You see live progress: what Dev is "thinking", what tools it's using, and results as they happen
4. Dev returns the finished code with an explanation

> **Note:** Developer tasks can take up to 5 minutes for complex work. The live progress feed keeps you informed.

---

### Scheduler Agent (Sched)

**When it activates:** Your message contains words like: *schedule, every Monday, recurring, automate, set up a job, weekly, daily, monthly*. Or go to the Scheduled Jobs section.

**What it does:**
- Creates, lists, updates, and deletes recurring automated tasks
- Any department agent can be scheduled (Sales, Finance, Marketing, Support, Management)
- Runs in the background on your specified schedule — no manual action needed

**Sample prompts:**

| What you want | What to type |
|--------------|-------------|
| Weekly sales report | `"Schedule a weekly sales pipeline report every Monday at 9am Singapore time"` |
| Daily finance check | `"Set up a daily revenue summary at 8am every weekday"` |
| Monthly marketing report | `"Create a monthly marketing performance report on the 1st of each month at 10am"` |
| List your jobs | `"Show me my scheduled jobs"` |
| Run a job now | `"Run my weekly sales report now"` |
| Delete a job | `"Delete the daily finance report job"` |

#### Understanding Schedules (Cron Format)

All schedules run in UTC internally. The AI converts your local time automatically:

| Your local time | UTC equivalent | What you say |
|----------------|:--------------:|-------------|
| 9:00 AM Singapore (SGT) | 1:00 AM UTC | "9am Singapore time" |
| 9:00 AM Hong Kong (HKT) | 1:00 AM UTC | "9am Hong Kong time" |
| 8:00 AM Malaysia (MYT) | 12:00 AM UTC | "8am Malaysia time" |
| 9:00 AM Mon–Fri SGT | 1:00 AM UTC, weekdays | "9am SGT weekdays" |

**You never need to know the cron format** — just describe the schedule in plain English and the AI converts it.

#### Schedule Limits

| Limit | Value |
|-------|-------|
| Maximum active jobs per user | 10 |
| Minimum interval between runs | 15 minutes |
| Available agents for scheduling | Sales, Finance, Marketing, Support, Management |

#### Managing Your Scheduled Jobs

| Action | What to say |
|--------|------------|
| See all jobs | `"List my scheduled jobs"` |
| Run a job immediately | `"Run my weekly sales report now"` |
| Delete a job | `"Delete the Monday sales report"` |
| Check job health | `"Show me my scheduled job status"` |

---

## Cross-Department Requests (Orchestration)

**What is orchestration?** When you ask a question that spans multiple departments (e.g., "Compare sales and finance performance"), the Management Agent automatically coordinates a multi-agent response.

### What triggers orchestration?

Your message must be sent from a **Management** account and contain comparison or multi-department keywords:

| Trigger phrase | Example |
|---------------|---------|
| `compare` | "Compare sales and marketing ROI" |
| `versus` / `vs` | "Q1 sales vs Q1 finance" |
| `across departments` | "Report across all departments" |
| `all departments` | "All departments performance this month" |
| `and sales` / `sales and` | "Finance and sales summary" |
| `both departments` | "Both departments KPI" |
| `multiple departments` | "Multiple departments review" |

### What happens step by step

1. **You send the request** from the Management portal
2. **Max (Management Agent) decomposes the task** — using AI to break it into specialist sub-tasks (e.g., "get sales data" → Sam, "get finance data" → Fiona)
3. **Sub-tasks run in parallel** where possible (faster results)
4. **Sequential sub-tasks wait** for the previous one to complete if they depend on each other
5. **Max synthesises all results** into a single executive summary
6. **Delivery:** The report is sent to Teams #management channel and emailed to leadership

### Example: Cross-Department Comparison

**You type:**
> "Compare sales and finance performance this quarter"

**What happens:**
- Sam (Sales Agent) queries the CRM: leads, pipeline, deals closed
- Fiona (Finance Agent) queries financials: revenue, expenses, margins
- Max synthesises both into an executive report
- Report delivered to Teams and emailed to you

**Expected time:** 2–5 minutes for a full multi-department report.

---

## Scheduled Jobs Reference

### Create a Scheduled Job

**Say:** `"Schedule a [frequency] [what report] for [agent] at [time] [timezone]"`

**Examples:**
- `"Schedule a weekly sales pipeline report every Monday at 9am SGT"`
- `"Set up a daily revenue summary for finance at 8am every weekday"`
- `"Create a monthly marketing report on the 1st of each month at 10am HKT"`

**The AI will confirm:**
- Job name
- Agent (Sales / Finance / Marketing / Support / Management)
- Schedule in plain English ("Every Monday at 1:00 AM UTC = 9:00 AM SGT")
- Next run time

### List Your Scheduled Jobs

**Say:** `"Show me my scheduled jobs"` or `"List my jobs"`

**You'll see:** Job name, agent, schedule description, next run time, status (active/inactive)

### Run a Job Immediately

**Say:** `"Run my [job name] now"` or `"Trigger the weekly sales report"`

If you refer to the job by name, the AI looks it up first, then runs it.

### Delete a Scheduled Job

**Say:** `"Delete the [job name]"` or `"Cancel my daily finance report"`

The AI looks up the job by name, confirms, then deletes it.

### Timezone Quick Reference

| City | Timezone | Say it as |
|------|----------|-----------|
| Singapore | SGT (+8) | "9am Singapore time" or "SGT" |
| Hong Kong | HKT (+8) | "9am Hong Kong time" or "HKT" |
| Kuala Lumpur | MYT (+8) | "8am Malaysia time" or "MYT" |
| Tokyo | JST (+9) | "9am Japan time" or "JST" |
| London | GMT (+0) | "9am London time" or "GMT" |

---

## File Storage Guide

When the AI generates a document (PDF, CSV, PowerPoint), it saves it in your file storage. You can request where to save it.

### Storage Levels

| Scope | Who can see it | Best for |
|-------|:-------------:|---------|
| **Personal** (default) | Only you | Your private reports, draft documents |
| **Department** | Your whole department | Team-shared reports, templates |
| **Company** | Everyone at Mezzofy | Company announcements, policies (Management write only) |

### How to request a specific folder

Add the destination to your request:

- `"Generate a sales report and save it to the Sales department folder"`
- `"Create a PDF summary and email it to me — save a copy to the company folder"`
- `"Export the data to CSV and save to my personal files"`

### Finding your files

**Say:** `"Find my sales report from last week"` or `"Search my files for the Q1 report"`

The AI searches across all folders you have access to.

---

## Tips & Tricks

### Attaching Files for Analysis

You can attach files directly in the chat:

| File type | What the AI can do |
|-----------|-------------------|
| **PDF** | Read, summarise, extract data, answer questions |
| **Image** (JPEG, PNG, WebP) | Describe, extract text (OCR), analyse contents |
| **CSV** | Read data, perform calculations, generate summaries |
| **DOCX / PPTX** | Read and summarise content |

**Example:** Attach a supplier contract PDF and ask: `"Summarise the key payment terms and flag any unusual clauses."`

### Requesting Different Output Formats

You can specify the output format in your request:

| Format | Say | Best for |
|--------|-----|---------|
| PDF | "as a PDF" | Reports, presentations to share |
| PowerPoint | "as a presentation" or "PPTX" | Slide decks for meetings |
| CSV | "as a CSV" or "export to CSV" | Data for analysis in Excel |
| Word document | "as a Word doc" or "DOCX" | Editable reports |
| Email | "email it to me" | Immediate delivery |
| Teams | "post to Teams" | Team-wide announcements |

### Using the Scheduler for Automated Reports

**Set it once, receive it every time:**

1. Decide what report you want and how often
2. Tell the Scheduler Agent: `"Schedule a weekly sales report every Monday at 9am SGT"`
3. The report runs automatically — you receive it in your inbox

**Common automated reports:**

| Report | Sample setup command |
|--------|---------------------|
| Weekly sales pipeline | `"Schedule a sales pipeline summary every Monday at 9am SGT"` |
| Daily revenue check | `"Set up a daily finance revenue report at 8am weekdays"` |
| Monthly marketing KPI | `"Monthly marketing performance report on the 1st at 10am"` |
| Weekly company KPI | `"Weekly company KPI dashboard every Friday at 4pm SGT"` |

### Getting the Best Research Results

For the Research Agent (Rex), more context = better results:

| Instead of | Try |
|-----------|-----|
| `"Research competitors"` | `"Research our top 5 competitors in B2B coupon exchange in Singapore — focus on pricing and customer reviews"` |
| `"What's happening in fintech?"` | `"Research latest fintech regulations in Singapore and Malaysia as of 2026 that affect coupon and loyalty platforms"` |
| `"Find companies in logistics"` | `"Research 10 mid-size logistics companies in Malaysia with 50–200 employees that could benefit from employee loyalty programs"` |

### Working Smarter with Your AI Team

| Scenario | Best approach |
|---------|--------------|
| Need a quick answer | Just ask — the AI responds immediately |
| Need a detailed report | Ask for it "as a PDF" — gets formatted properly |
| Need something every week | Use the Scheduler Agent to automate it |
| Researching a market or competitor | Use Research Agent with a detailed question |
| Need code or automation | Use Developer Agent with a clear description |
| Comparing multiple departments | Use Management account with "compare" or "vs" keywords |
| Sharing with your team | Ask AI to "post to Teams" or "save to department folder" |

---

*Mezzofy AI Assistant — User Guide v2.0*
*For technical architecture details, see [AGENTS.md](AGENTS.md)*
*For the full feature list, see [Mezzofy_AI_Assistant_Features_List_v2.0.md](Mezzofy_AI_Assistant_Features_List_v2.0.md)*
