# TD — Chat Flow Map — mz-ai-assistant Server
**Version:** v1.0
**Date:** 2026-03-09
**Agent:** Lead
**Purpose:** Document every path from user input to response

---

## Layer 1: Entry Points (How a message arrives)

```
4 Entry Points → all converge on route_request()
─────────────────────────────────────────────────────────────────
A  POST /chat/send          text message (most common)
B  POST /chat/send-media    image / video / audio / file upload
C  POST /chat/send-url      URL to scrape
D  WS   /chat/ws            real-time: speech, camera, text
```

---

## Layer 2: The Critical Fork — Sync vs Background

For entry points A, B, C (REST), the FIRST decision splits everything:

```
POST /chat/send (chat.py:104)
  │
  ├─ Auth: JWT verified by middleware → user in request.state
  │
  └─ _is_long_running(message)?   (chat.py:96–99)
      Keywords: research, report, generate pdf, create pdf, analyze all,
                weekly, monthly, compare, pitch deck, scrape, linkedin
      │
      ├─ YES → BACKGROUND PATH (chat.py:129–196)
      │         ├─ Create/get session in DB
      │         ├─ INSERT agent_tasks row (status='queued')
      │         ├─ Pre-save user message to conversations
      │         ├─ process_chat_task.delay(payload)  ← Celery
      │         └─ RETURN 202 { status:"queued", task_id, session_id }
      │
      └─ NO  → SYNC PATH (chat.py:198–248)
                ├─ process_input(task)  ← extract/normalize text
                ├─ Get or create session in DB
                ├─ Task limit check (mobile only)
                │   └─ running_count >= 3? → RETURN error (TASK_LIMIT_REACHED)
                ├─ route_request(task)  ← agent selection + execution
                ├─ process_result()     ← save to DB + build response
                └─ RETURN 200 { response, artifacts, session_id, ... }
```

---

## Layer 3: Input Processing (before routing)

```
process_input(task)  — app/input/input_router.py
  │
  ├─ input_type = "text"   → passthrough (extracted_text = message)
  ├─ input_type = "image"  → vision analysis (OCR/classification)
  ├─ input_type = "video"  → frame extraction + analysis
  ├─ input_type = "audio"  → speech-to-text (Whisper)
  ├─ input_type = "file"   → PDF text extraction
  ├─ input_type = "url"    → web scraping + content extraction
  └─ unknown               → log warning, treat as text

  Output: task dict + { extracted_text, media_content, input_summary }
```

---

## Layer 4: Agent Selection (router.py)

```
route_request(task)  — app/router.py:38
  │
  ├─ source == "webhook"
  │   └─ _route_webhook()
  │       └─ Match task["event"] → _WEBHOOK_EVENT_AGENT map
  │           ├─ "customer_signed_up"  → SalesAgent
  │           ├─ "support_ticket_created" → SupportAgent
  │           ├─ "employee_onboarded"  → HRAgent
  │           ├─ "employee_offboarded" → HRAgent
  │           └─ No match → ERROR { "No handler registered" }
  │
  ├─ source == "scheduler"
  │   └─ _route_scheduler()
  │       └─ Use task["agent"] OR task["department"] → execute by name
  │
  └─ source == "mobile" (or any other)
      └─ _route_mobile()
          └─ get_agent_for_task(task)  — agent_registry.py:45
              │
              ├─ Step 1: department in AGENT_MAP?
              │   ├─ "finance"    → FinanceAgent
              │   ├─ "hr"         → HRAgent
              │   ├─ "sales"      → SalesAgent
              │   ├─ "marketing"  → MarketingAgent
              │   ├─ "support"    → SupportAgent
              │   └─ "management" → ManagementAgent
              │
              ├─ Step 2: Unknown dept + cross_dept permission
              │   (role in {admin, executive, management} OR has permission)
              │   └─ Try every agent's can_handle(task) keyword match
              │       ├─ First match → use that agent
              │       └─ No match → Step 3
              │
              └─ Step 3: DEFAULT → SalesAgent
```

---

## Layer 5: LLM Model Selection (llm_manager.py:104–129)

```
select_model(message, context)
  │
  ├─ _contains_chinese(message)?   [CJK Unicode chars present]
  │   └─ YES → Kimi  (typically fails — no KIMI_API_KEY in .env)
  │
  ├─ _is_chinese_market_task(message, context)?
  │   apac_signals = { "china", "chinese market", "mainland", "apac",
  │                    "mandarin", "中国", "亚太", "新加坡" }
  │   OR department in ("apac", "china", "asia")
  │   └─ YES → Kimi  (typically fails)
  │
  └─ DEFAULT → Claude (claude-sonnet-4-5-20250929)
```

**Note:** English city/country names (singapore, malaysia, taiwan, hong kong) were
removed from `apac_signals` in commit `63db1b7` to prevent false Kimi routing.

---

## Layer 6: Agent Execution (6 Agents × N Workflows)

### ManagementAgent
```
can_handle(): dept="management" AND message has KPI keyword

execute():
  ├─ scheduler + "kpi_report" → _weekly_kpi_workflow()
  │     Query metrics → LLM → PDF → Teams (#management) + email CEO/COO
  ├─ message has KPI keyword  → _kpi_dashboard_workflow()
  │     Query 3 dept metrics + LLM usage → LLM → PDF
  └─ ELSE                     → _general_response()  ← LLM + full tool access
```

### FinanceAgent
```
can_handle(): dept="finance" (no keyword required)

execute():
  ├─ scheduler/webhook                      → financial workflow
  ├─ message has financial keyword          → financial workflow
  │     Detect type (p&l/balance/cashflow)
  │     → financial_query() → LLM → PDF → (if automated) Teams + CFO email
  └─ mobile without financial keyword       → _general_response()
```

### SalesAgent  ← also the DEFAULT fallback agent
```
can_handle(): dept="sales" (no keyword required)

execute():
  ├─ scheduler + "follow"                   → _daily_followup_workflow()
  │     CRM stale leads → compose emails → send → Teams (#sales)
  ├─ webhook + "customer_signed_up"         → _customer_onboarding_workflow()
  │     Save to CRM → welcome email → Teams (#sales)
  ├─ pitch keywords (pitch deck, deck, ...)  → _pitch_deck_workflow()
  │     Web research → create_pitch_deck() → PPTX artifact
  ├─ linkedin keywords                      → _prospecting_workflow()
  │     LinkedIn search → save leads → send intro emails (max 5)
  └─ ELSE                                   → _general_sales_workflow()
        Product info → LLM → response
```

### SupportAgent
```
can_handle(): dept="support" (no keyword required)

execute():
  ├─ scheduler + "support_summary"          → _weekly_summary_workflow()
  │     Ticket analysis (7 days) → LLM → PDF → Teams (#support) + email
  ├─ webhook + "support_ticket_created"     → _ticket_triage_workflow()
  │     Classify severity → KB lookup → Teams alert → (high) escalate email
  ├─ message has support keyword            → _ticket_analysis_workflow()
  │     Analyze tickets → LLM → PDF
  └─ ELSE                                   → _general_response()
```

### MarketingAgent
```
can_handle(): dept="marketing" (no keyword required)

execute():
  ├─ message has marketing keyword          → content generation workflow
  │     Detect: type + tone + length + audience
  │     → generate_content() → PDF (playbook) or DOCX (website)
  └─ ELSE                                   → _general_response()
```

### HRAgent
```
can_handle(): dept="hr" (no keyword required)

execute():
  ├─ scheduler + "weekly_hr_summary"        → _weekly_hr_summary_workflow()
  ├─ scheduler + "monthly_headcount"        → _headcount_report_workflow()
  ├─ webhook + "employee_onboarded"         → _onboarding_workflow()
  ├─ webhook + "employee_offboarded"        → _offboarding_workflow()
  ├─ message: payroll/salary keywords       → _payroll_query_workflow()
  ├─ message: leave/attendance keywords     → _leave_query_workflow()
  ├─ message: recruit/hiring keywords       → _recruitment_query_workflow()
  └─ ELSE                                   → _general_response()
```

---

## Layer 7: LLM Tool-Calling Loop (llm_manager.py:161–367)

```
execute_with_tools(task)
  │
  ├─ select_model() → Claude or Kimi
  ├─ _build_system_prompt(dept, role, source)
  ├─ Get all tool definitions (28+ tools)
  │
  └─ FOR i in 0..4 (MAX_TOOL_ITERATIONS = 5):
      │
      ├─ model.chat(history, tools=defs, system=prompt)
      │   ON PRIMARY FAIL → retry with fallback model (Kimi ↔ Claude)
      │   ON BOTH FAIL:
      │     ├─ artifacts already created? → return success with files
      │     └─ ELSE → return ERROR "AI service unavailable"
      │
      ├─ response has tool_calls?
      │   │
      │   ├─ NO → FINAL ANSWER → RETURN { content, artifacts, tools_used }
      │   │
      │   └─ YES → for each tool_call:
      │             ├─ tool_executor.execute(tool_name, **args)
      │             ├─ ON TOOL ERROR → RETURN immediately (no retry)
      │             ├─ Capture artifact if file_path returned
      │             └─ Append tool exchange to history → next iteration
      │
      └─ Reached max 5 iterations → RETURN partial answer
```

**Available Tool Groups (28+ tools):**

| Group | Tools |
|-------|-------|
| Email/Calendar | outlook_send_email, outlook_read_emails, outlook_reply_email, outlook_batch_send, outlook_search_emails, outlook_create_event, outlook_get_events, outlook_find_free_slots |
| Teams | teams_send_message, teams_post_channel |
| Documents | create_pdf, read_pdf, merge_pdfs, create_pptx, create_docx, create_csv, create_text |
| Web | browser_browse, scraping_scrape, linkedin_search |
| Data | query_analytics, crm_create_lead, crm_get_lead, mezzofy_query, knowledge_search |
| Media | image_analyze, video_process, audio_transcribe |
| Push | push_send_notification |

---

## Layer 8: Post-Processing & Response (processor.py)

```
process_result(task, agent_result, session)
  │
  ├─ agent_task_id present? (background task)
  │   ├─ YES → skip user message save (pre-saved in chat.py)
  │   └─ NO  → append_message(user message)
  │
  ├─ append_message(assistant response)
  │
  ├─ Register artifacts in DB (for each file in raw_artifacts)
  │
  ├─ agent_task_id present?
  │   ├─ YES → UPDATE agent_tasks SET status='completed'
  │   └─ NO  → INSERT agent_tasks (new sync task record)
  │
  └─ Build & RETURN response envelope:
      {
        "session_id": str,
        "response": str,            ← agent's text content
        "input_processed": dict,    ← e.g. "Image: 2000x1500 jpg"
        "artifacts": [
          { "id", "type", "name", "download_url" }
        ],
        "agent_used": str,          ← "finance", "sales", etc.
        "tools_used": list[str],
        "success": bool,
        "task_id": str
      }
```

---

## Layer 9: Background Task Delivery (tasks.py — after agent.execute)

```
_run_chat_task() — after process_result() + db.commit():
  │
  ├─ Publish to Redis channel → WebSocket picks up → sends to mobile
  └─ Push notification (if device_token in task)
      ├─ SUCCESS → send "Your report is ready" notification
      └─ FAILURE → send "Task failed" notification
```

---

## Layer 10: WebSocket Path (chat.py:517–657)

```
WS /chat/ws?token=JWT
  │
  ├─ Auth: extract JWT from query param
  ├─ Register connection in WebSocket manager
  ├─ Subscribe to Redis pub/sub: user:{user_id}:notifications
  │
  └─ Listen loop:
      │
      ├─ msg_type = "speech_start"   → initialize speech buffer
      ├─ msg_type = "speech_audio"   → add PCM chunk to buffer
      ├─ msg_type = "speech_end"     → SpeechOps.transcribe() → treat as text
      ├─ msg_type = "camera_frame"   → ImageOps.analyze() → send result to WS
      └─ msg_type = "text"           → _handle_ws_text()
                                          route_request(task) → agent.execute()
                                          send response to WS
```

---

## All Possible Response Types

| Scenario | HTTP | Body shape |
|----------|:----:|------------|
| Short message → LLM response | 200 | `{ response, session_id, task_id, success:true }` |
| Long-running → queued | 202 | `{ status:"queued", task_id, session_id }` |
| Task limit exceeded (mobile) | 200 | `{ success:false, code:"TASK_LIMIT_REACHED" }` |
| No agent found for webhook event | 200 | `{ success:false, content:"No handler registered..." }` |
| All LLMs fail | 200 | `{ success:false, content:"AI service temporarily unavailable" }` |
| Tool fails mid-loop | 200 | `{ success:false, content:"Tool error..." }` |
| Response with files | 200 | `{ response, artifacts:[{pdf/pptx/csv}], success:true }` |
| WebSocket response | WS frame | Same envelope, pushed via send_json() |
| Background complete | WS push | Redis → WS → `{ type:"task_complete", task_id, response }` |

---

## Background Task State Machine

```
agent_tasks.status:

  queued  →  running  →  completed
    │            │
    │            └─  failed  (SoftTimeLimitExceeded or max retries)
    │
    └─  cancelled  (POST /tasks/{id}/cancel)

Retry policy: 2 retries, 10s backoff (for non-timeout exceptions)
Timeout:      9 min soft → mark failed, no retry
              10 min hard (Celery task_time_limit)
```

---

## Files Involved (Critical Paths)

| File | Role |
|------|------|
| `server/app/api/chat.py` | All HTTP endpoints + sync/async fork |
| `server/app/router.py` | Agent selection by source + department |
| `server/app/agents/agent_registry.py` | Department → Agent mapping + fallback |
| `server/app/agents/*_agent.py` | 6 agent implementations + workflow branching |
| `server/app/agents/base_agent.py` | `_general_response()` fallback for all agents |
| `server/app/llm/llm_manager.py` | Model selection + tool-calling loop |
| `server/app/llm/anthropic_client.py` | Claude API with rate-limit retry |
| `server/app/llm/kimi_client.py` | Kimi API (currently broken — no API key) |
| `server/app/tasks/tasks.py` | Celery background task (process_chat_task) |
| `server/app/context/processor.py` | Save to DB + build response envelope |
| `server/app/input/input_router.py` | Multi-modal input normalization |
| `server/app/tools/tool_executor.py` | 28+ tool dispatch |

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-03-09 | Initial chat flow map (post-deployment analysis) |
