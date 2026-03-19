# Plan: WebSocket Push for Agent Office
**Version:** v1.43.0
**Date:** 2026-03-19
**Author:** Lead Agent
**Workflow:** Change Request
**Status:** READY TO EXECUTE

---

## Objective

Replace the 8-second HTTP polling for agent status with real-time WebSocket push.
Any task created by any user or agent triggers an instant push to the Agent Office canvas,
causing the assigned agent to walk to the Task Room immediately.

---

## Architecture

```
[Any user / Celery worker]
        │
        ▼
  INSERT agent_tasks          ← Publish #1: status='queued'
  (chat.py REST endpoint)
        │
        ▼
  Celery picks up task        ← Publish #2: status='running'
  (_update_agent_task_status)
        │
        ▼
  Task completes/fails        ← Publish #3: status='completed'|'failed'
  (_update_agent_task_done/failed)

All 3 publishes → Redis channel: admin:agent-status

[Admin Portal WebSocket]
        │
        ├── Connects to: GET /api/admin-portal/ws?token=<JWT>
        ├── Subscribes to: admin:agent-status
        └── Receives instant push → updates agent list state → canvas reacts
```

---

## Redis Pub/Sub Message Format

```json
{
  "type": "agent_status",
  "department": "finance",
  "status": "queued" | "running" | "completed" | "failed",
  "task_title": "Generate Q1 report",
  "agent_task_id": "uuid"
}
```

---

## Phase 1 — Backend (Backend Agent, 1 session)

### Task B1: Add Redis publish at task creation (chat.py)

**File:** `server/app/api/chat.py`

**Where:** Inside `POST /send` and `POST /send-media` handlers, immediately after the
`INSERT INTO agent_tasks` with `status='queued'`, before `apply_async()` Celery dispatch.

**Publish:**
```python
await redis_client.publish("admin:agent-status", json.dumps({
    "type": "agent_status",
    "department": department,
    "status": "queued",
    "task_title": title,
    "agent_task_id": str(agent_task_id)
}))
```

### Task B2: Add Redis publish at status transitions (tasks.py)

**File:** `server/app/workers/tasks.py` (or `server/app/tasks/tasks.py`)

**Where:** Inside the 3 existing status update functions:
- `_update_agent_task_status()` → publish `status='running'`
- `_update_agent_task_done()` → publish `status='completed'`
- `_update_agent_task_failed()` → publish `status='failed'`

Note: These are sync functions called from Celery workers (not async). Use the sync Redis
client (already available) or `redis.from_url(...).publish(...)` synchronously.

### Task B3: New admin WebSocket endpoint (admin_portal.py)

**File:** `server/app/api/admin_portal.py`

**Add new route:**
```
GET /api/admin-portal/ws?token=<JWT>
```

**Logic:**
1. Validate JWT from query param (reuse existing `get_current_user` pattern from chat.py WS)
2. Accept WebSocket connection
3. Create async Redis subscriber on channel `admin:agent-status`
4. Forward every Redis message directly to the WebSocket client
5. On disconnect: unsubscribe and clean up

**Auth:** Admin role check — only users with `role='admin'` can connect.

**Resilience:** If Redis message fails to parse, log and continue (don't crash WS).

### Task B4: Register route in main.py / router

Ensure the new admin WS endpoint is registered. Check if `admin_portal.py` router is
already included — if yes, no change needed to main.py.

### Quality Gate — Backend Complete When:
- [ ] `POST /chat/send` publishes to `admin:agent-status` on task create
- [ ] `_update_agent_task_status('running')` publishes to `admin:agent-status`
- [ ] `_update_agent_task_done()` publishes to `admin:agent-status`
- [ ] `_update_agent_task_failed()` publishes to `admin:agent-status`
- [ ] `GET /api/admin-portal/ws` accepts JWT, subscribes Redis, forwards messages
- [ ] Manual test: `wscat -c "wss://assistant.mezzofy.com/api/admin-portal/ws?token=<JWT>"` receives events when a chat message is sent

---

## Phase 2 — Frontend (Frontend Agent, 1 session)

### Task F1: Add useAgentOfficeWS hook (new file)

**File:** `portal/src/hooks/useAgentOfficeWS.ts`

**Logic:**
- Connect to `wss://assistant.mezzofy.com/api/admin-portal/ws?token=<JWT>`
- Get JWT from auth store (Zustand)
- On message: parse JSON, update agent status in local state
- On disconnect: attempt reconnect with exponential backoff (max 5 retries)
- On unmount: close connection

**State shape the hook manages:**
```typescript
// Override map — keyed by department
type AgentOverrides = Record<string, { is_busy: boolean; current_task: string | null }>
```

### Task F2: Update DashboardPage.tsx

**File:** `portal/src/pages/DashboardPage.tsx`

**Changes:**
1. Import and call `useAgentOfficeWS()`
2. Merge WS overrides into the React Query agent list:
   ```typescript
   const mergedAgents = agentList.map(agent => ({
     ...agent,
     is_busy: wsOverrides[agent.department]?.is_busy ?? agent.is_busy,
     current_task: wsOverrides[agent.department]?.current_task ?? agent.current_task,
   }))
   ```
3. Change `refetchInterval: 8000` → `refetchInterval: 60000` (REST poll as fallback only)
4. Pass `mergedAgents` to `<AgentOffice>` instead of raw `agentList`

### Task F3: Update AgentOffice canvas for 'queued' state

**File:** `portal/src/components/AgentOffice.tsx`

**Current states:** idle | walking | at-table-running
**Add:** queued state (agent walking toward Task Room with "QUEUING" bubble instead of "RUNNING")

**Change in status bubble logic:**
- If `agentStatus === 'queued'` and agent is walking → show orange `⏳ QUEUING` bubble
- If `agentStatus === 'running'` and at table → show existing `● RUNNING` bubble

The AgentStatus type needs a `current_status` field added alongside `is_busy`:
```typescript
interface AgentStatus {
  // existing fields...
  is_busy: boolean
  current_task: string | null
  current_status?: 'queued' | 'running' | 'completed' | 'failed'  // NEW
}
```

### Quality Gate — Frontend Complete When:
- [ ] WS hook connects on DashboardPage mount
- [ ] Sending a chat message causes the target agent to start walking within <1 second
- [ ] Agent shows `⏳ QUEUING` bubble while walking
- [ ] Agent shows `● RUNNING` when seated at Task Room table
- [ ] Agent walks back to desk on `completed` or `failed` event
- [ ] If WS disconnects, portal falls back to 60s REST poll (no broken UI)
- [ ] No console errors on mount/unmount

---

## Phase 3 — Deploy (1 step, human-executed)

```bash
# Push to GitHub via GitHub Desktop
# Then on EC2:
ssh -i mz-ai-key.pem ubuntu@3.1.255.48
cd /home/ubuntu/mz-ai-assistant && git pull
sudo systemctl restart mezzofy-api.service
cd portal && npm run build
```

Service restart is required because a new WebSocket route is added to FastAPI.

---

## Execution Order

```
Phase 1 (Backend) ──→ Phase 2 (Frontend) ──→ Phase 3 (Deploy)
  [sequential]           [sequential]            [human]
```

Backend must complete first — Frontend F1/F2/F3 depend on the WS endpoint existing.

---

## Agent Assignments

| Agent | Tasks | Sessions |
|-------|-------|---------|
| Backend Agent | B1, B2, B3, B4 | 1 session |
| Frontend Agent | F1, F2, F3 | 1 session |

---

## Files Modified

**Backend:**
- `server/app/api/chat.py` — add publish after agent_task INSERT
- `server/app/workers/tasks.py` (or tasks/tasks.py) — add publish in 3 status update functions
- `server/app/api/admin_portal.py` — add `/ws` WebSocket endpoint

**Frontend:**
- `portal/src/hooks/useAgentOfficeWS.ts` — NEW hook
- `portal/src/pages/DashboardPage.tsx` — use WS hook, merge overrides, slow down REST poll
- `portal/src/components/AgentOffice.tsx` — add queued status bubble
- `portal/src/types/index.ts` — add `current_status` field to AgentStatus

---

## Version

Portal: `1.42.0` → `1.43.0`
Server: stays at current version (additive change, no schema migration needed)
