# TESTING.md — Testing Plan & Success Criteria

**Department workflow tests, API endpoint tests, security tests, and success criteria.**

---

## Test Categories

```
1. Connection Tests       → scripts/test.py (pre-startup)
2. API Endpoint Tests     → auth, chat, chat-media, files, webhooks, scheduler, admin
3. Input Processing Tests → image, video, audio, speech, file, URL, camera
4. Department Workflows   → Finance, Sales, Marketing, Support, Management
5. Scheduled Job Tests    → Celery Beat cron, task execution, delivery
6. Webhook Tests          → Ingestion, signature verification, agent routing
7. MS Teams Integration   → Post messages, receive mentions, file uploads
8. Security Tests         → RBAC, rate limiting, data scoping
9. LLM Integration        → Claude, Kimi, failover
10. Tool Tests            → Outlook email/calendar, Teams, PDF, PPTX, LinkedIn, CRM, DB, media
```

---

## 1. Connection Tests (`scripts/test.py`)

Run before server startup to verify environment is ready.

| Test | What It Checks | Pass Condition |
|------|---------------|---------------|
| `test_postgresql()` | PostgreSQL reachable, tables exist | Connection + query succeeds |
| `test_redis()` | Redis reachable | PING returns PONG |
| `test_celery()` | Celery workers connected to Redis broker | Worker ping succeeds |
| `test_claude_api()` | Anthropic API key valid | Simple completion succeeds |
| `test_kimi_api()` | Kimi/Moonshot API key valid | Simple completion succeeds |
| `test_ms_graph()` | MS 365 Graph API authentication | Token acquisition succeeds |
| `test_config()` | `config.yaml` valid, required fields present | All fields exist |
| `test_directories()` | `/data`, `/knowledge`, `/logs` exist | All directories present |
| `test_playwright()` | Chromium browser available | Browser launches |

---

## 2. API Endpoint Tests

### Auth Endpoints

| Test | Description | Expected |
|------|-------------|----------|
| Login with valid credentials | POST /auth/login | 200 + JWT tokens |
| Login with wrong password | POST /auth/login | 401 Unauthorized |
| Access protected endpoint without token | POST /chat/send | 401 |
| Access with expired token | POST /chat/send | 401 + "Token expired" |
| Refresh token flow | POST /auth/refresh | New access token |

### Chat Endpoints

| Test | Description | Expected |
|------|-------------|----------|
| Send text message | POST /chat/send | 200 + response text |
| Send image + message | POST /chat/send-media (image) | 200 + image analysis + response |
| Send video | POST /chat/send-media (video) | 200 + transcript + scene analysis |
| Send audio file | POST /chat/send-media (audio) | 200 + transcript + response |
| Send PDF | POST /chat/send-media (file) | 200 + extracted text + response |
| Send URL | POST /chat/send-url | 200 + scraped content + response |
| Send oversized video (>100MB) | POST /chat/send-media | 413 Payload Too Large |
| Send unsupported file type | POST /chat/send-media (.exe) | 415 Unsupported Media Type |
| Send message with new session | Omit session_id | 200 + new session_id |
| Get chat history | GET /chat/history/{id} | Messages in order (incl. media messages) |
| List sessions | GET /chat/sessions | User's sessions |
| WebSocket connection | WS /chat/ws | Status updates streamed |
| WebSocket live speech | WS speech_start → audio chunks → speech_end | Partial transcripts + final text |
| WebSocket live camera | WS camera_frame (JPEG) | Real-time camera analysis |

---

## 3. Input Processing Tests

### Image Processing

| Test | Description | Expected |
|------|-------------|----------|
| JPEG image with text | Upload receipt photo | OCR extracts text, Vision describes content |
| PNG screenshot | Upload app screenshot | Vision describes UI elements |
| HEIC from iPhone | Upload HEIC photo | Converted + processed correctly |
| Large image (>2048px) | Upload 4K photo | Resized before Vision API |
| Image with no text | Upload landscape photo | Description returned, OCR empty |
| Corrupt image file | Upload invalid file | Error: "Unable to process image" |

### Video Processing

| Test | Description | Expected |
|------|-------------|----------|
| MP4 with speech | Upload meeting recording | Audio transcribed, key frames analyzed |
| Short video (<30s) | Upload quick clip | Processed without frame skipping |
| Long video (5 min) | Upload full recording | Key frames at 5s intervals, full transcript |
| Video > 5 min | Upload 10 min video | Rejected: "Maximum duration exceeded" |
| Video with no audio | Upload silent screen recording | Frame analysis only, no transcript |

### Audio Processing

| Test | Description | Expected |
|------|-------------|----------|
| MP3 English speech | Upload voice memo | English transcript returned |
| M4A Chinese speech | Upload Mandarin audio | Chinese transcript, language detected |
| WAV meeting recording | Upload 30 min meeting | Full transcript returned |
| Audio > 50MB | Upload large file | Rejected: size limit exceeded |

### Live Speech (WebSocket)

| Test | Description | Expected |
|------|-------------|----------|
| English speech stream | Send audio chunks via WS | Partial transcripts → final text |
| Chinese speech stream | Send Mandarin audio chunks | Chinese transcript returned |
| Start/stop cycle | Multiple speech sessions | Each session handled independently |
| Empty audio chunks | Send silence | No transcript, no error |

### Live Camera (WebSocket)

| Test | Description | Expected |
|------|-------------|----------|
| Send camera frame | JPEG frame via WS | Description returned |
| Rapid frames | 10 frames in 5 seconds | Rate limited to 1 fps processing |
| Business card photo | Frame of business card | Contact info extracted |

### File Processing

| Test | Description | Expected |
|------|-------------|----------|
| PDF with text | Upload text-heavy PDF | Full text extracted |
| PDF with tables | Upload financial PDF | Tables + text extracted |
| DOCX document | Upload Word doc | Text + headings extracted |
| PPTX presentation | Upload slides | Slide text + notes extracted |
| CSV data file | Upload data CSV | Parsed as structured data |
| XLSX spreadsheet | Upload Excel file | All sheets parsed |

### URL Processing

| Test | Description | Expected |
|------|-------------|----------|
| Valid public URL | Send company website | Text + screenshot + contact info |
| URL with tables | Send page with data tables | Tables extracted as structured data |
| URL timeout | Send very slow page | Timeout error after 30s |
| Internal IP URL | Send http://192.168.x.x | Rejected: "Internal URLs not allowed" |
| Invalid URL | Send "not-a-url" | Validation error |

### File Endpoints

| Test | Description | Expected |
|------|-------------|----------|
| Download own file | GET /files/{id} | 200 + file bytes |
| Download another user's file | GET /files/{id} | 403 Forbidden |
| List files | GET /files/list | Own files only |

---

## 3. Department Workflow Tests

### Finance: Generate & Email Financial Statement

```
Input:  "Generate the latest financial statement and send to CEO"
User:   finance_manager role

Expected flow:
  1. Router → Finance Agent
  2. database_query → fetch financial data
  3. LLM formats statement
  4. pdf_generator → branded PDF created
  5. email_send → PDF sent to CEO email
  6. Artifact stored in /data/documents

Verify:
  ✅ PDF exists and contains valid financial data
  ✅ Email sent (check email_log table)
  ✅ Artifact recorded in artifacts table
  ✅ Response includes download link
  ✅ Audit log entry created
```

### Sales: LinkedIn Lead Generation + Email Outreach

```
Input:  "Find 20 F&B companies in Singapore on LinkedIn and send intro emails"
User:   sales_rep role

Expected flow:
  1. Router → Sales Agent
  2. linkedin_search → extract company profiles
  3. web_scraper → gather additional info
  4. crm_save → insert leads with status "new"
  5. LLM composes personalized emails
  6. email_send → batch send with rate limiting
  7. crm_update → mark leads as "contacted"
  8. csv_export → generate leads CSV

Verify:
  ✅ Leads saved in sales_leads table
  ✅ Emails sent (check email_log, rate limiting respected)
  ✅ Lead status updated to "contacted"
  ✅ CSV artifact generated
  ✅ Response includes lead count + CSV download
```

### Sales: Generate Pitch Deck

```
Input:  "Create a pitch deck for ABC Restaurant Group"
User:   sales_rep role

Expected flow:
  1. Router → Sales Agent
  2. mezzofy_data → fetch products, pricing, features
  3. web_research → research ABC Restaurant Group
  4. crm_query → check existing CRM records
  5. LLM generates slide content
  6. pptx_generator → create branded PPTX

Verify:
  ✅ PPTX file generated with correct slide structure
  ✅ Customer name appears on slides
  ✅ Mezzofy branding applied (template used)
  ✅ Artifact stored + download link returned
```

### Marketing: Website Content + Playbook

```
Input:  "Write website content and playbook for our new loyalty feature"
User:   marketing_creator role

Expected flow:
  1. Router → Marketing Agent
  2. mezzofy_data → fetch loyalty feature specs
  3. knowledge_base → load brand guidelines
  4. LLM generates website copy
  5. LLM generates playbook content
  6. Save .md (website copy) + .pdf (playbook)

Verify:
  ✅ Website copy follows brand voice
  ✅ Playbook PDF is well-structured
  ✅ Product details are accurate
  ✅ Both artifacts stored + download links
```

### Support: Weekly Ticket Summary

```
Input:  "Summarize this week's support tickets and flag recurring issues"
User:   support_agent role

Expected flow:
  1. Router → Support Agent
  2. database_query → fetch week's tickets
  3. LLM categorizes and analyzes
  4. LLM generates summary with action items
  5. pdf_generator → weekly report

Verify:
  ✅ Summary covers correct date range
  ✅ Recurring issues identified
  ✅ PDF report generated
```

### Management: Cross-Department KPI Dashboard

```
Input:  "Give me a KPI dashboard across all departments this month"
User:   executive role

Expected flow:
  1. Router → Management Agent
  2. Multiple database queries (sales, support, marketing, finance, llm_usage)
  3. LLM synthesizes executive summary
  4. pdf_generator → KPI report

Verify:
  ✅ Data from all departments included
  ✅ LLM usage costs tracked
  ✅ Summary highlights key metrics + concerns
  ✅ Executive has access to all department data (RBAC verified)
```

---

## 5. Scheduled Job Tests

| Test | Description | Expected |
|------|-------------|----------|
| Celery Beat fires weekly KPI | Simulate cron trigger | Management Agent executes, PDF generated |
| Celery Beat fires monthly financial | Simulate 1st-of-month trigger | Finance Agent executes, PDF generated |
| Celery Beat fires daily lead followup | Simulate weekday 10AM trigger | Sales Agent queries stale leads, sends emails |
| Celery Beat fires weekly support | Simulate Friday 5PM trigger | Support Agent summarizes tickets |
| Teams delivery | Scheduled job completes | PDF posted to correct Teams channel |
| Outlook email delivery | Scheduled job completes | PDF emailed to configured recipients |
| User creates scheduled job | POST /scheduler/jobs | Job saved to scheduled_jobs table |
| User deletes scheduled job | DELETE /scheduler/jobs/{id} | Job deactivated |
| User without permission | POST /scheduler/jobs (no scheduler_manage) | 403 Forbidden |
| User creates job for wrong dept | POST /scheduler/jobs (sales user, finance agent) | 403 Forbidden |
| Audit logging | Any scheduled job runs | audit_log entry with source="scheduler" |
| Job failure handling | Agent throws error | Job marked failed, no crash, error logged |

---

## 6. Webhook Tests

| Test | Description | Expected |
|------|-------------|----------|
| Mezzofy customer_signed_up | POST /webhooks/mezzofy with valid signature | 200 OK, Celery task queued |
| Valid signature | HMAC-SHA256 matches payload | Webhook accepted |
| Invalid signature | Wrong HMAC | 401 Unauthorized |
| Missing signature | No X-Mezzofy-Signature header | 401 Unauthorized |
| customer_signed_up processing | Full event flow | Lead added to CRM, welcome email sent, Teams notified |
| support_ticket_created | Full event flow | Ticket triaged, #support notified, escalation if severe |
| customer_churned | Full event flow | Management alerted in Teams |
| Unknown event type | POST with unsupported event | Logged but not processed |
| Rate limiting | 101 webhook events in 1 minute | 429 after limit |
| Webhook event logging | Any webhook received | webhook_events row created |
| Teams @mention webhook | Bot mentioned in Teams | Agent processes, replies in channel |
| Custom webhook (Zapier) | POST /webhooks/custom/zapier | Accepted with valid secret |

---

## 7. MS Teams Integration Tests

| Test | Description | Expected |
|------|-------------|----------|
| Post text to channel | teams_post_message to #sales | Message appears in Teams |
| Post with file attachment | PDF attached to Teams message | File uploaded + linked |
| Send DM | teams_send_dm to specific user | DM delivered in Teams |
| List channels | teams_list_channels | All department channels returned |
| Channel mapping | Channel name "sales" → actual channel ID | Correct channel resolved |
| Invalid channel | Post to non-existent channel | Graceful error |
| MS Graph auth | Acquire token from Azure AD | Token cached, auto-refreshed |
| MS Graph rate limit | Many Teams posts in succession | Rate limiting respected |

---

## 8. Security Tests

### RBAC Enforcement

| Test | Description | Expected |
|------|-------------|----------|
| Sales rep accesses finance data | Query financial tables | 403 Forbidden |
| Finance user creates sales lead | Call crm_save tool | Permission denied |
| Marketing user sends email | Use email_send | Allowed (has email_send permission) |
| Support agent views audit logs | Query audit_log | 403 (no audit_read permission) |
| Executive reads all departments | Multiple queries | Allowed |
| Admin does everything | Any action | Allowed |

### Data Scoping

| Test | Description | Expected |
|------|-------------|----------|
| Sales rep lists leads | search_leads | Only own leads returned |
| Sales manager lists leads | search_leads | All sales leads returned |
| User downloads other's file | GET /files/{other_id} | 403 Forbidden |

### Rate Limiting

| Test | Description | Expected |
|------|-------------|----------|
| 31st request in 1 minute | POST /chat/send | 429 Too Many Requests |
| 31st email in 1 hour | email_send tool | Rate limit error |
| 51st LinkedIn search | linkedin_search tool | Rate limit error |

---

## 9. LLM Integration Tests

| Test | Description | Expected |
|------|-------------|----------|
| Claude basic response | Simple question | Text response returned |
| Claude tool calling | Request needing PDF | Tool called, PDF generated |
| Kimi Chinese content | Chinese language message | Kimi selected, Chinese response |
| Failover Claude → Kimi | Simulate Claude timeout | Kimi handles request |
| Failover Kimi → Claude | Simulate Kimi timeout | Claude handles request |
| Token tracking | Any request | llm_usage row created |

---

## 10. Tool Tests

| Tool | Test | Expected |
|------|------|----------|
| `outlook_send_email` | Send test email via MS Graph | Email delivered via Outlook, email_log entry |
| `outlook_read_emails` | Read inbox | Recent emails returned |
| `outlook_create_event` | Create calendar event | Event appears in Outlook calendar |
| `outlook_get_events` | Read events for date range | Events returned |
| `teams_post_message` | Post to #sales channel | Message appears in Teams |
| `teams_send_dm` | Send DM to user | DM delivered |
| `create_pdf` | Generate from text | Valid PDF file created |
| `create_pptx` | Generate from template | Valid PPTX with slides |
| `linkedin_search` | Search companies | Structured results returned |
| `create_lead` | Insert lead | Row in sales_leads |
| `query_db` | SELECT query | Data returned, no mutations |
| `query_db` | Attempt INSERT | Rejected (read-only) |
| `get_products` | Fetch product data | JSON with products |
| `search_knowledge` | Search templates | Matching results |
| `ocr_image` | Extract text from image | OCR text returned |
| `analyze_image` | Describe photo content | Vision description returned |
| `transcribe_audio` | Audio file → text | Transcript returned |
| `extract_key_frames` | Video → frames | JPEG frames extracted |
| `stream_stt` | Audio chunks → text | Partial + final transcripts |

---

## Success Criteria Summary

### Core System

- [ ] FastAPI server starts and responds to health check
- [ ] PostgreSQL connected, all tables created (including scheduled_jobs, webhook_events)
- [ ] Redis connected, rate limiting functional
- [ ] Celery workers connected and processing tasks
- [ ] Celery Beat running and firing scheduled jobs
- [ ] Claude API responds to requests
- [ ] Kimi API responds to requests
- [ ] MS Graph API authenticated (Outlook + Teams)
- [ ] Nginx proxies HTTPS correctly
- [ ] WebSocket streaming works end-to-end

### Mobile App → Server

- [ ] Login returns JWT tokens
- [ ] Text chat messages processed and responded to
- [ ] Image upload → OCR + Vision analysis → AI response
- [ ] Video upload → frame extraction + transcription → AI response
- [ ] Audio upload → Whisper transcription → AI response
- [ ] File upload (PDF/DOCX/PPTX/CSV) → text extraction → AI response
- [ ] URL submission → Playwright scrape → AI response
- [ ] Live speech via WebSocket → real-time partial transcripts → final response
- [ ] Live camera via WebSocket → real-time frame analysis
- [ ] Generated files downloadable via API
- [ ] Push notifications delivered for async tasks
- [ ] WebSocket status updates streamed during multi-step tasks
- [ ] Oversized/unsupported uploads rejected with clear error messages

### Department Workflows

- [ ] Finance: Financial statement PDF generated and emailed via Outlook
- [ ] Sales: LinkedIn leads scraped, saved to CRM, emails sent via Outlook
- [ ] Sales: Pitch deck PPTX generated from template
- [ ] Marketing: Website content + playbook PDF created
- [ ] Support: Ticket summary with recurring issues
- [ ] Management: Cross-department KPI report

### Scheduled Jobs (Celery Beat)

- [ ] Weekly KPI report auto-generated Monday 9AM → Teams #management + executive emails
- [ ] Monthly financial summary auto-generated 1st of month → Teams #finance + CFO email
- [ ] Daily stale lead follow-up fires weekdays 10AM → Outlook emails + Teams #sales
- [ ] Weekly support summary fires Friday 5PM → Teams #support + manager email
- [ ] User-created scheduled jobs saved and executed on schedule
- [ ] Job results delivered via MS Teams and/or Outlook
- [ ] All scheduled job executions logged in audit_log

### Webhooks

- [ ] Mezzofy product webhooks accepted with valid HMAC signature
- [ ] customer_signed_up → lead added to CRM + welcome email + Teams notification
- [ ] support_ticket_created → ticket triaged + Teams notification
- [ ] Invalid webhook signatures rejected with 401
- [ ] All webhook events logged in webhook_events table
- [ ] MS Teams @mention → agent processes and replies in channel

### MS Teams Integration

- [ ] Post messages to department channels (sales, finance, marketing, support, management)
- [ ] Upload file attachments to Teams messages (PDFs, CSVs)
- [ ] Send direct messages to individual users
- [ ] Receive and process @mentions from Teams channels

### MS 365 Outlook Integration

- [ ] Send emails via Microsoft Graph API (not SMTP)
- [ ] Read inbox for email tools
- [ ] Create calendar events (meetings, reminders, deadlines)
- [ ] Read calendar events for scheduling tools
- [ ] All sent emails logged in email_log table

### Security

- [ ] Unauthorized users cannot access API
- [ ] RBAC enforced at gateway and agent levels
- [ ] Data scoped by department and role
- [ ] Rate limiting prevents abuse (including webhooks)
- [ ] All actions logged to audit_log (mobile, scheduler, webhook, teams sources)
- [ ] SQL injection prevented (parameterized queries)
- [ ] File access restricted to owner + permitted users
- [ ] MS 365 OAuth token auto-refreshed
- [ ] Webhook HMAC signatures verified
- [ ] Celery workers isolated (no shell access)

---

## Running Tests

```bash
# Pre-startup connection tests
python scripts/test.py

# API tests (with server running)
pytest tests/api/ -v

# Department workflow tests
pytest tests/workflows/ -v

# Security tests
pytest tests/security/ -v

# Full suite
pytest tests/ -v --tb=short
```
