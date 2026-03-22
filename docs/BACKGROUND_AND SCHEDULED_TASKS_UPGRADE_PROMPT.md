Audit and upgrade the Mezzofy AI Assistant project at ~/mz-ai-assistant to use
Celery + Redis for all background tasks and scheduled tasks, and add a Background
Tasks management page to the portal UI.

This upgrade must ensure tasks survive TWO restart scenarios:
  (A) FastAPI service restart  → sudo systemctl restart mz-ai-assistant
  (B) Full server reboot       → sudo reboot
Both scenarios must be verified explicitly in Phase 4.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — AUDIT CURRENT BACKGROUND TASK IMPLEMENTATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Map the full project structure — identify every file that runs background
   tasks, async jobs, or long-running agent processes.

2. Check if Celery is already in use:
   - Is celery in requirements.txt or pip list?
   - Is there a celery_app.py or tasks/ folder?
   - Is redis-server running? (check: systemctl is-active redis-server)
   - Are any @celery.task decorators present in the codebase?

3. Identify all current background task patterns in use:
   - asyncio.create_task(...)
   - BackgroundTasks from FastAPI
   - ThreadPoolExecutor or ProcessPoolExecutor
   - APScheduler (AsyncIOScheduler, BackgroundScheduler)
   - Any asyncio.sleep loops acting as schedulers
   - Any other fire-and-forget patterns
   - Check crontab: crontab -l

4. List every agent and what its background task produces:
   - Agent name
   - Task type (PPTX, PDF, DOCX, XLSX, research, outreach, etc.)
   - Output/deliverable (file path, message, data)
   - Current task tracking method (if any)
   - Whether it is a one-off task or a scheduled/recurring task

5. For each scheduled job found, record:
   - Job name and what it does
   - Schedule (cron expression, interval, one-off)
   - Currently running inside FastAPI process or as a separate process?
   - Whether missed runs are tracked or silently dropped
   - Risk level: CRITICAL (in-process) or SAFE (separate process)

Report all findings before proceeding to Phase 2.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — INFRASTRUCTURE: REDIS + CELERY + PERSISTENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

── 2a. Install Dependencies ──

  pip install celery redis flower redbeat
  sudo apt install -y redis-server

── 2b. Redis Persistence Configuration ──

CRITICAL: By default Redis stores data in memory only. A full server reboot
will wipe all task history, schedules, and in-flight state. Fix this by
enabling AOF (Append Only File) persistence:

  sudo nano /etc/redis/redis.conf

  Set these values:
    appendonly yes
    appendfilename "appendonly.aof"
    appendfsync everysec
    auto-aof-rewrite-percentage 100
    auto-aof-rewrite-min-size 64mb

  Restart Redis to apply:
    sudo systemctl restart redis-server

  Verify persistence is active:
    redis-cli config get appendonly
    # Must return: appendonly → yes

  Enable Redis to start on server boot:
    sudo systemctl enable redis-server

  Verify Redis survives reboot (check after Phase 4 reboot test):
    redis-cli ping  # must return PONG after reboot

── 2c. Core Celery Setup ──

Create celery_app.py at project root ~/mz-ai-assistant/celery_app.py:

  from celery import Celery
  from redbeat import RedBeatScheduler

  app = Celery("mz_ai")

  app.conf.update(
      # Redis DB separation: broker=0, backend=1, beat=2
      broker_url="redis://localhost:6379/0",
      result_backend="redis://localhost:6379/1",
      redbeat_redis_url="redis://localhost:6379/2",

      # Task behaviour
      task_track_started=True,
      task_serializer="json",
      result_serializer="json",
      accept_content=["json"],
      result_expires=86400,  # 24 hours

      # Scheduler
      beat_scheduler="redbeat.RedBeatScheduler",

      # Worker reliability
      worker_prefetch_multiplier=1,
      task_acks_late=True,  # only ack after task completes, not when picked up
      task_reject_on_worker_lost=True,  # requeue if worker dies mid-task

      # Include all task modules
      include=[
          "tasks.document_tasks",
          "tasks.agent_tasks",
          "tasks.outreach_tasks",
      ]
  )

── 2d. Task Registry (required for GET /api/tasks list endpoint) ──

Celery's Redis backend stores results by task_id only — there is no built-in
index. To support listing all tasks, maintain a separate registry in Redis DB 1.

Create tasks/registry.py:

  import redis
  import json
  from datetime import datetime

  _r = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
  REGISTRY_KEY = "mz:task:index"

  def register_task(task_id: str, meta: dict):
      meta["task_id"] = task_id
      meta["registered_at"] = datetime.utcnow().isoformat()
      _r.hset(REGISTRY_KEY, task_id, json.dumps(meta))

  def get_all_tasks(status=None, agent=None, limit=50, offset=0):
      all_tasks = [json.loads(v) for v in _r.hvals(REGISTRY_KEY)]
      all_tasks.sort(key=lambda x: x.get("registered_at", ""), reverse=True)
      if status:
          all_tasks = [t for t in all_tasks if t.get("status") == status]
      if agent:
          all_tasks = [t for t in all_tasks if t.get("agent") == agent]
      return all_tasks[offset:offset + limit]

  def remove_task(task_id: str):
      _r.hdel(REGISTRY_KEY, task_id)

── 2e. Task Definitions ──

Create tasks/ folder:
  tasks/__init__.py
  tasks/registry.py          (as above)
  tasks/document_tasks.py    → PPTX, PDF, DOCX, XLSX generation + QA loops
  tasks/agent_tasks.py       → Research agent, Developer agent, other agents
  tasks/outreach_tasks.py    → Lead gen, CRM enrichment, outreach (if present)

Each task must:
  - Use @celery.task(bind=True, name="mz.<task_name>")
  - Call self.update_state() at each major step with a human-readable status:
      PENDING → STARTED → GENERATING → QA_RENDERING → QA_INSPECTING →
      COMPLETED / FAILED
  - Call tasks.registry.register_task() immediately when task starts
  - Store in meta at every state update:
      {
        "task_id": "<celery task id>",
        "agent": "<agent name>",
        "task_type": "<PPTX|PDF|DOCX|XLSX|research|etc>",
        "description": "<what this task is doing>",
        "status": "<current status string>",
        "output_path": "<file path or null>",
        "output_url": "<download URL or null>",
        "progress": 0-100,
        "started_at": "<ISO timestamp>",
        "updated_at": "<ISO timestamp>",
        "error": "<error message or null>"
      }
  - On completion store deliverable path/URL so portal can link to it
  - On failure store full error message and traceback summary

For document generation tasks, implement the full QA loop per format:
  PPTX: generate → soffice convert to PDF → pdftoppm →
        read slide images → pass to Claude as base64 → fix issues → re-render
  PDF:  generate → pdftoppm → read page images →
        pass to Claude as base64 → fix issues → re-render
  DOCX: generate → validate.py → grep placeholders →
        soffice → pdftoppm → view → fix → re-render
  XLSX: generate → recalc.py → fix formula errors → re-run until clean

Note: soffice must be invoked as "soffice" not "libreoffice".
Note: docx npm package is local — all node scripts must run with
      cwd=/home/ubuntu/mz-ai-assistant so node_modules/docx is found.

── 2f. Migrate Existing Background Tasks ──

Replace every existing background task pattern with Celery:
  - asyncio.create_task(fn()) → fn_task.delay()
  - background_tasks.add_task(fn) → fn_task.delay()
  - executor.submit(fn) → fn_task.delay()
  - APScheduler jobs → Celery Beat with redbeat (see Phase 2g)

Each migration must:
  - Return task_id immediately to the caller
  - Not break any existing API contract (same endpoints, add task_id to response)
  - Remove all APScheduler initialisation from FastAPI startup events

── 2g. Migrate Scheduled Tasks to Celery Beat + redbeat ──

For every scheduled/recurring task found in Phase 1 that is CRITICAL
(running inside FastAPI process), migrate to Celery Beat:

  In celery_app.py add to app.conf.beat_schedule:
    {
        "<job_name>": {
            "task": "tasks.<module>.<function_name>",
            "schedule": crontab(hour=9, minute=0),
            "options": {"expires": 3600}
        }
    }

  redbeat persists the schedule in Redis DB 2. After migration:
  - The schedule survives FastAPI restart (Beat is a separate process)
  - The schedule survives full server reboot (Redis AOF restores DB 2)
  - Missed runs during downtime are tracked, not silently dropped

── 2h. FastAPI Task Management Endpoints ──

Add to the FastAPI router (prefix: /api/tasks):

  GET  /api/tasks
       Returns list from tasks.registry (not Celery backend directly).
       Support query params: ?status=PENDING|STARTED|COMPLETED|FAILED|REVOKED
                             ?agent=<agent_name>
                             ?limit=50&offset=0

  GET  /api/tasks/stats
       Returns counts by status from the registry.
       IMPORTANT: declare this route BEFORE /api/tasks/{task_id} to avoid
       FastAPI treating "stats" as a task_id parameter.

  GET  /api/tasks/{task_id}
       Returns single task detail from Celery backend + registry meta.
       Map Celery state REVOKED → display as CANCELLED in response.

  POST /api/tasks/{task_id}/cancel
       Calls: celery.control.revoke(task_id, terminate=True, signal="SIGTERM")
       Note: terminate=True is required to stop already-running tasks.
             Without it, revoke only prevents queued tasks from starting.
       Updates registry meta status to CANCELLED.
       Returns: {"task_id": ..., "status": "CANCELLED"}

  DELETE /api/tasks/{task_id}
       Calls: AsyncResult(task_id).forget()
       Removes from registry: tasks.registry.remove_task(task_id)

  GET  /api/tasks/scheduled
       Lists all redbeat schedule entries from Redis DB 2.
       Returns: job name, schedule expression, next_run, last_run, is_paused.

  POST /api/tasks/scheduled/{name}/run
       Triggers the scheduled task immediately via .delay()
       Returns: {"task_id": ..., "status": "STARTED"}

  POST /api/tasks/scheduled/{name}/pause
       Disables the redbeat entry without deleting it.

  POST /api/tasks/scheduled/{name}/resume
       Re-enables a paused redbeat entry.

── 2i. Systemd Services ──

Create /etc/systemd/system/mz-celery.service:

  [Unit]
  Description=Mezzofy AI Celery Worker
  After=network.target redis-server.service
  Requires=redis-server.service

  [Service]
  User=ubuntu
  WorkingDirectory=/home/ubuntu/mz-ai-assistant
  ExecStartPre=/bin/sh -c 'until redis-cli ping; do sleep 1; done'
  ExecStart=/home/ubuntu/mz-ai-assistant/server/venv/bin/celery \
      -A celery_app worker --loglevel=info --concurrency=4
  Restart=always
  RestartSec=5
  KillSignal=SIGTERM
  TimeoutStopSec=60

  [Install]
  WantedBy=multi-user.target

Create /etc/systemd/system/mz-celery-beat.service:

  [Unit]
  Description=Mezzofy AI Celery Beat Scheduler
  After=network.target redis-server.service mz-celery.service
  Requires=redis-server.service

  [Service]
  User=ubuntu
  WorkingDirectory=/home/ubuntu/mz-ai-assistant
  ExecStartPre=/bin/sh -c 'until redis-cli ping; do sleep 1; done'
  ExecStart=/home/ubuntu/mz-ai-assistant/server/venv/bin/celery \
      -A celery_app beat --loglevel=info
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target

Create /etc/systemd/system/mz-flower.service (internal monitoring):

  [Unit]
  Description=Mezzofy AI Celery Flower Monitor
  After=mz-celery.service

  [Service]
  User=ubuntu
  WorkingDirectory=/home/ubuntu/mz-ai-assistant
  ExecStart=/home/ubuntu/mz-ai-assistant/server/venv/bin/celery \
      -A celery_app flower --port=5555
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target

Enable and start all services:
  sudo systemctl daemon-reload
  sudo systemctl enable redis-server mz-celery mz-celery-beat mz-flower
  sudo systemctl start mz-celery mz-celery-beat mz-flower

Note: ExecStartPre health check ensures Celery never starts before Redis is
ready, preventing connection failures after reboot.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — PORTAL UI: BACKGROUND TASKS PAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Locate the portal frontend (React or whatever framework is in use).
Add a "Background Tasks" menu item in the sidebar below "Messages".

IMPORTANT: Build the full tabbed structure upfront in this phase.
Do not build a single-tab page and retrofit tabs later.

── 3a. Sidebar Navigation ──

Add menu item:
  Icon: clock or queue icon
  Label: "Background Tasks"
  Badge: live count of PENDING + STARTED tasks (updates every 10 seconds)
  Route: /tasks

── 3b. Background Tasks Page (/tasks) ──

Build a full-page task management view with two tabs:
  Tab 1: "Active Tasks"     → live queue (default tab)
  Tab 2: "Scheduled Tasks"  → recurring jobs and upcoming runs

SHARED HEADER (above tabs):
  - Page title: "Background Tasks"
  - Stats bar: [All: N] [Running: N] [Completed: N] [Failed: N] [Cancelled: N]
  - Refresh button (manual) + auto-refresh toggle (every 10s, on by default)

── TAB 1: Active Tasks ──

Filter row:
  - Status filter: All | Running | Completed | Failed | Cancelled
  - Agent filter: All | <agent names from API>

Task list (one card per task):
  ┌─────────────────────────────────────────────────────────────────┐
  │ [Status Badge]  Task Description          Agent      Started    │
  │                 PPTX: Mezzofy Intro Deck  Dev Agent  10:23 AM  │
  │                 ████████░░ 80%            3 mins ago            │
  │                 Current step: QA_RENDERING slide 2 of 3        │
  │                 [Download ↓]  [View Log]  [Kill ✕]             │
  └─────────────────────────────────────────────────────────────────┘

Status badges (Mezzofy brand colours):
  - PENDING   → grey badge
  - STARTED   → orange pulsing badge (#f97316)
  - COMPLETED → black badge with ✓
  - FAILED    → red badge with ✗
  - CANCELLED → grey badge with strikethrough
  Note: Celery state REVOKED maps to display label CANCELLED

Progress bar:
  - Orange fill (#f97316) on white background
  - Shows 0-100% from task meta.progress
  - Only shown for STARTED tasks

Actions per task:
  - [Download ↓] → only when COMPLETED and output_path exists
                   links to file download endpoint
  - [View Log]   → expands inline showing step-by-step status history
                   with timestamps for each state transition
  - [Kill ✕]     → only for PENDING or STARTED tasks
                   confirmation dialog: "Cancel this task? This cannot
                   be undone." → POST /api/tasks/{id}/cancel
                   uses terminate=True to stop already-running tasks
                   button turns grey and disabled immediately after click

Empty state:
  "No background tasks yet. Tasks created by agents will appear here."

Error state:
  "Could not connect to task queue. Check that the Celery worker is running."

── TAB 2: Scheduled Tasks ──

Shows all redbeat schedule entries from GET /api/tasks/scheduled.

Table columns: Job Name | Schedule | Next Run | Last Run | Status | Actions

Each row:
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Daily Report    Every day 9am   Tomorrow 9:00   ✓ Today    Active   │
  │ Weekly Sync     Mon 8am         Mon 22 Apr      ✓ Mon 15   Active   │
  │ [Run Now]  [Pause]                                                   │
  └──────────────────────────────────────────────────────────────────────┘

Status indicators:
  - Active  → green dot
  - Paused  → grey dot
  - Last Run ✓ → success (links to task detail in Active Tasks tab)
  - Last Run ✗ → failed (links to task detail, highlights in red)

Actions per scheduled job:
  - [Run Now]  → POST /api/tasks/scheduled/{name}/run
                 triggers immediately, new task appears in Active Tasks tab
  - [Pause]    → POST /api/tasks/scheduled/{name}/pause
                 row status changes to Paused, button changes to [Resume]
  - [Resume]   → POST /api/tasks/scheduled/{name}/resume

Empty state:
  "No scheduled tasks configured."

── 3c. Task Detail Panel ──

Clicking any task row opens a side panel or expanded section showing:
  - Full task ID (copyable)
  - Agent assigned
  - Task type and full description
  - Complete status history with timestamps (audit trail)
  - Full error message and Python traceback if FAILED
  - Deliverable: file name, size, download button
  - Raw meta JSON (collapsed by default, expandable for debugging)

── 3d. Real-time Updates ──

Poll GET /api/tasks every 10 seconds and update rows in place.
Do not full-reload the page — only update changed rows.
Sidebar badge updates on the same poll cycle.

Transition highlights:
  - COMPLETED: row flashes light orange (#fef3ea) for 3 seconds
  - FAILED: row flashes light red for 3 seconds
  - CANCELLED: row immediately greys out

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 — VERIFY EVERYTHING WORKS END TO END
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run ALL verification steps. Report pass/fail for each one.

── 4a. Service Health ──

  redis-cli ping
  # Expected: PONG

  celery -A celery_app inspect ping
  # Expected: worker responds

  sudo systemctl status mz-celery mz-celery-beat mz-flower
  # Expected: all active (running)

  redis-cli config get appendonly
  # Expected: appendonly → yes  (confirms persistence is on)

── 4b. Basic Task Flow ──

  python3 -c "
  from tasks.document_tasks import generate_pptx_task
  result = generate_pptx_task.delay('Test deck', '/tmp/test.pptx')
  print('Task ID:', result.id)
  print('Status:', result.state)
  "

  curl http://localhost:8000/api/tasks/<task_id>
  # Expected: task detail with meta, progress, status

  curl http://localhost:8000/api/tasks
  # Expected: list including the test task above

── 4c. Kill Test ──

  # Submit a task, immediately cancel it
  POST /api/tasks/<task_id>/cancel
  # Expected: status → CANCELLED (even if task was already running)

  # Confirm terminate=True worked for an already-running task:
  # Submit a slow task, let it start (status=STARTED), then cancel.
  # Status must become CANCELLED, not stay STARTED.

── 4d. SCENARIO A — FastAPI Service Restart ──

  # Submit a long-running task (e.g. PPTX with QA loop)
  # Confirm status = STARTED
  sudo systemctl restart mz-ai-assistant

  # Poll immediately after restart
  curl http://localhost:8000/api/tasks/<task_id>
  # Expected: task continues running, status still updates
  # Task must complete successfully — Celery worker was not restarted

── 4e. SCENARIO B — Full Server Reboot ──

  # Submit a scheduled task trigger via portal [Run Now] or API
  # Note its task_id
  # Check redbeat entries before reboot:
  redis-cli -n 2 keys "redbeat:*"
  # Note the count

  sudo reboot
  # Wait for server to come back up (~60-90 seconds)

  # After reboot, verify all services auto-started:
  sudo systemctl status redis-server mz-celery mz-celery-beat mz-flower

  # Verify Redis data survived:
  redis-cli ping
  redis-cli -n 2 keys "redbeat:*"
  # Expected: same redbeat entries as before reboot

  # Verify task history survived:
  curl http://localhost:8000/api/tasks
  # Expected: previous tasks still in list with correct status

  # Verify Celery worker is connected:
  celery -A celery_app inspect ping

── 4f. Scheduled Task Verification ──

  # Trigger a scheduled task manually
  curl -X POST http://localhost:8000/api/tasks/scheduled/<name>/run
  # Expected: task appears in Active Tasks tab

  # Pause a scheduled job
  curl -X POST http://localhost:8000/api/tasks/scheduled/<name>/pause
  # Verify: row shows Paused status in portal

  # Resume it
  curl -X POST http://localhost:8000/api/tasks/scheduled/<name>/resume
  # Verify: row shows Active status in portal

── 4g. Portal Verification ──

  - "Background Tasks" appears in sidebar below "Messages"
  - Badge shows correct live PENDING + STARTED count
  - Active Tasks tab: tasks show correct status, progress, agent
  - Download link works for a completed document task
  - Kill button cancels a running task (confirm terminate works)
  - Scheduled Tasks tab: all jobs listed with correct next run times
  - Run Now button triggers a task and it appears in Active Tasks
  - Auto-refresh updates list every 10s without page reload
  - REVOKED state from Celery displays as CANCELLED in portal

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSTRAINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Do not break any existing API endpoints or frontend routes
- Do not remove any existing agent logic — only wrap it in Celery tasks
- Do not delete any existing scheduled job logic — only migrate it
- Keep all file paths consistent with the existing project structure
- docx npm package is local at ~/mz-ai-assistant/node_modules/docx —
  all node scripts must run with cwd=/home/ubuntu/mz-ai-assistant
- LibreOffice must be invoked as soffice (not libreoffice)
- Brand colours: primary orange #f97316, black #000000, white #ffffff,
  light orange #fef3ea — apply to all new portal UI components
- All new Python files must run inside the venv at
  /home/ubuntu/mz-ai-assistant/server/venv
- Redis DB separation: broker=DB0, backend=DB1, beat=DB2
- Celery state REVOKED must always display as CANCELLED in the portal
- GET /api/tasks/stats route must be declared BEFORE /api/tasks/{task_id}
  in the FastAPI router to avoid route parameter collision
- task_acks_late=True and task_reject_on_worker_lost=True must be set
  to prevent task loss if a worker dies mid-execution
- ExecStartPre health check (redis-cli ping loop) is required in all
  Celery systemd services to prevent startup race conditions after reboot
- Report each phase completion with pass/fail results before starting next
- Scheduled task history must appear in the same Background Tasks portal
  page as regular tasks (unified view via two tabs)