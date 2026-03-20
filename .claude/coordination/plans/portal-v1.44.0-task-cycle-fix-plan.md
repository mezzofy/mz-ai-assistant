# Plan: Full Task Cycle Fix (Mobile → Backend → Portal)
**Version:** v1.44.0
**Date:** 2026-03-20
**Status:** READY TO EXECUTE

---

## Root Causes

1. `/tasks/active` hides completed tasks — both mobile and portal polling never see them
2. Mobile `onTaskComplete` WS callback never fetches result or adds chat message
3. `agent_tasks.result` stores `{success, artifacts}` — no response text field

---

## Backend Agent Tasks (B1–B3)

### B1 — Add response text to agent_tasks.result (processor.py)

File: `server/app/context/processor.py`

In `process_result()`, find the UPDATE that sets `result = CAST(:result AS jsonb)`.
The current `_result_payload` is `{ success: True, artifacts: [...] }`.
Add the response text:

```python
_result_payload = {
    "success": True,
    "response": agent_response_text,   # ADD: the actual LLM response string
    "artifacts": [...]
}
```

Find where `agent_response_text` (or equivalent — the LLM response string) is available
in that function and include it. Look at what `process_result()` receives as parameters
(likely `agent_result` dict) and extract the text from it.

### B2 — Add result field to GET /tasks/active (tasks.py)

File: `server/app/api/tasks.py`

In the `/tasks/active` SELECT, add `result` to the column list AND extend the WHERE
clause to include recently-completed tasks:

```sql
WHERE user_id = :uid
  AND (
    status IN ('queued', 'running')
    OR (status IN ('completed', 'failed') AND completed_at > NOW() - INTERVAL '5 minutes')
  )
ORDER BY created_at DESC
```

This allows mobile/portal polling to see the completed task for 5 minutes after completion,
giving the UI time to fetch and display the result.

Also add `result` to the SELECT list so the response text is returned.

### B3 — Include response text in Redis task_complete notification (tasks.py)

File: `server/app/tasks/tasks.py`

In the Redis publish block (around line 534-546), extend the notification payload to
include the full response text (not just truncated summary):

```python
notification_payload = json.dumps({
    "type": "task_complete",
    "task_id": agent_task_id or celery_task_id,
    "session_id": str(session["id"]),
    "message": summary,           # keep existing truncated summary
    "response": full_response,    # ADD: full LLM response text
    "file_url": file_url,
})
```

Find where `full_response` is available in that function scope.

### After Backend Tasks

Git commit:
```
git add server/app/context/processor.py server/app/api/tasks.py server/app/tasks/tasks.py
git commit -m "fix(backend): task cycle — result text in agent_tasks, active endpoint shows recently-completed, WS payload includes full response"
```

---

## Mobile Agent Tasks (M1–M2)

### M1 — Fix onTaskComplete WS callback to show result in chat (chatStore.ts)

File: `APP/src/stores/chatStore.ts`

The current `onTaskComplete` callback only updates activeTask state. Fix it to:

1. Call `GET /tasks/{data.task_id}` to fetch the full task record with result
2. Extract response text from `task.result.response` (after backend fix, this will be there)
3. Add as assistant message to the chat messages array
4. THEN update activeTask to status='completed' (which triggers the 3s dismiss)

Import the tasks API function (check if `getTaskById` or `GET /tasks/{id}` exists in
`APP/src/api/chat.ts` — if not, add it).

```typescript
// In onTaskComplete callback:
const onTaskComplete = async (data: {task_id: string; session_id: string; message: string; response?: string; file_url: string | null}) => {
  // 1. Use response from WS payload if available, otherwise fetch task
  let responseText = data.response || data.message
  if (!responseText) {
    try {
      const taskResult = await getTaskByIdApi(data.task_id)
      responseText = taskResult.result?.response || taskResult.result?.reply || data.message
    } catch { responseText = data.message }
  }

  // 2. Add as chat message
  if (responseText) {
    const newMsg = { id: Date.now(), role: 'assistant' as const, text: responseText, time: getTimeStr() }
    set(s => ({ messages: [...s.messages, newMsg] }))
  }

  // 3. Update task state (triggers banner dismiss)
  set(s => ({
    activeTask: s.activeTask?.id === data.task_id
      ? {...s.activeTask, status: 'completed' as const}
      : s.activeTask,
  }))
  get().loadTasks()
}
```

### M2 — Fix pollActiveTask to show result when task appears as completed

File: `APP/src/stores/chatStore.ts`

In `pollActiveTask()`, when a task with `status === 'completed'` is found:
- Extract `task.result?.response`
- Add as assistant message to chat (same as M1 above)
- Set activeTask to the completed task (so the dismiss timer fires)

```typescript
pollActiveTask: async (sessionId: string) => {
  const result = await getActiveTasksApi()
  if (get().sessionId !== sessionId) return
  const task = result.tasks.find(t => t.session_id === sessionId) ?? null

  // NEW: if task completed, add response to chat
  if (task && task.status === 'completed' && task.result?.response) {
    const responseText = task.result.response
    const existing = get().messages
    const alreadyShown = existing.some(m => m.role === 'assistant' && m.text === responseText)
    if (!alreadyShown) {
      const newMsg = { id: Date.now(), role: 'assistant' as const, text: responseText, time: getTimeStr() }
      set(s => ({ messages: [...s.messages, newMsg] }))
    }
  }

  set({ activeTask: task })
}
```

Also add `getTaskByIdApi` to `APP/src/api/chat.ts` if missing:
```typescript
export const getTaskByIdApi = (taskId: string): Promise<TaskSummary> =>
  apiFetch<TaskSummary>(`/tasks/${taskId}`)
```

### After Mobile Tasks

TypeScript check: `cd APP && npx tsc --noEmit`

Git commit:
```
git add APP/src/stores/chatStore.ts APP/src/api/chat.ts
git commit -m "fix(mobile): show LLM response in chat when background task completes via WS or polling"
```

---

## Frontend Agent Tasks (F1–F2)

### F1 — Fix portal polling to use task-specific endpoint

File: `portal/src/components/AgentChatDialog.tsx`

Currently polls `getActiveTasks(sessionId)` which:
1. Returns all active tasks (not session-filtered on backend)
2. Completed tasks disappear from this list

Fix: Poll `GET /tasks/{taskId}` directly using the taskId from the 202 response.

Add to `portal/src/api/portal.ts`:
```typescript
getTaskById: (taskId: string) => client.get(`/tasks/${taskId}`),
```

In AgentChatDialog polling loop, replace `getActiveTasks(sessionId)` with:
```typescript
const taskRes = await portalApi.getTaskById(backgroundTaskId)
const task = taskRes.data
if (task.status === 'completed' || task.status === 'failed') {
  stopPolling()
  setSending(false)
  const result = extractTaskResult(task)
  // replace loading bubble with result
}
// If still queued/running → update loading bubble text with status
```

### F2 — Fix extractTaskResult for new result format

File: `portal/src/components/AgentChatDialog.tsx`

Update `extractTaskResult()` to handle `{success, response, artifacts}`:
```typescript
function extractTaskResult(task: ActiveTask): string {
  const r = task.result
  if (!r) return 'Task completed.'
  if (typeof r === 'string') return r
  if (typeof r.response === 'string' && r.response) return r.response
  if (typeof r.reply === 'string' && r.reply) return r.reply
  if (r.artifacts && r.artifacts.length > 0) {
    return `Task completed. ${r.artifacts.length} artifact(s) generated.`
  }
  if (typeof r.message === 'string') return r.message
  return 'Task completed successfully.'
}
```

### After Frontend Tasks

TypeScript check: `cd portal && npx tsc --noEmit`

Git commit:
```
git add portal/src/components/AgentChatDialog.tsx portal/src/api/portal.ts
git commit -m "fix(portal): poll task-by-id for completion, fix result extraction in AgentChatDialog"
```

---

## Execution Order

```
Backend (B1–B3) ──┐
Mobile  (M1–M2) ──┼──→ All complete → Deploy EC2 → Rebuild Portal → Build Mobile APK
Portal  (F1–F2) ──┘
```

All 3 agents can run IN PARALLEL (independent files).

---

## Deploy Checklist

```bash
# After all agents complete and GitHub Desktop push:
ssh -i mz-ai-key.pem ubuntu@3.1.255.48
cd /home/ubuntu/mz-ai-assistant && git pull
sudo systemctl restart mezzofy-api.service mezzofy-celery.service mezzofy-beat.service
cd portal && npm run build
```

Mobile: rebuild APK (v1.32.0) after mobile changes.

---

## Expected Result After Fix

1. User sends "Draft Merchant Agreement" in Mobile Chat
2. Backend returns 202 with task_id
3. Mobile shows ⏳ task banner
4. Portal Agent Office: Leo moves to Task Room (via admin WS push)
5. Portal polls GET /tasks/{taskId} → shows status: running
6. Celery completes → publishes to Redis with full response text
7. Mobile WS fires onTaskComplete → response added to chat → banner dismisses
8. Push notification sent if app is backgrounded
9. Portal polls GET /tasks/{taskId} → status: completed → result extracted → shown in dialog
10. Leo walks back to desk (via admin WS push: status='completed')
