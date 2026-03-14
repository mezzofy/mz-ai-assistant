# CLAUDE CODE TASK — Mezzofy AI: Multi-Agent Orchestration System

## MISSION
Review the entire existing project codebase and replace the current single-call AI handler 
with a full multi-agent orchestration system featuring agentic loops, background job processing, 
real-time WebSocket progress tracking, and two specialized agents:
  1. Research Agent  — Claude API with web_search_20250305 + Kimi API with $web_search
  2. Developer Agent — Claude Code running headless (--output-format stream-json)

Do NOT break any existing functionality. Extend it. All existing routes, UI, and integrations 
must remain working after this change.

---

## STEP 1 — CODEBASE AUDIT (do this first, before writing any code)

Read and understand the following before making any changes:

1. Find the current AI handler / chat completion function — note:
   - Where it lives (file path)
   - Which API it calls (Claude / Kimi / both)
   - How it's invoked (HTTP route, function call, etc.)
   - What it returns to the frontend
   - Whether it streams or returns a full response

2. Find the existing frontend chat component — note:
   - How it sends queries to the backend
   - How it renders AI responses
   - Whether it uses WebSocket, SSE, or REST

3. Find any existing job/task queue logic (if any)

4. Check CLAUDE.md for project conventions (colors, components, naming, patterns)

5. List all files you will create or modify before starting

Output a brief audit summary as a code comment at the top of your first new file.

---

## STEP 2 — BACKEND: MULTI-AGENT ORCHESTRATION

### 2a. Task Queue System

Create a background task management system with the following structure:

```
Task {
  id:           string (uuid short)
  agent:        "research" | "developer"
  query:        string
  status:       "queued" | "running" | "done" | "failed"
  result:       string | null
  steps:        Step[]
  client_id:    string
  created_at:   ISO timestamp
  completed_at: ISO timestamp | null
}

Step {
  type:     "start" | "thinking" | "tool_call" | "tool_result" | "output" | "done" | "error"
  message:  string
  tool:     string | null
  timestamp: ISO timestamp
}
```

Use FastAPI BackgroundTasks for async execution.
Store tasks in-memory dict for now (add a TODO comment for Redis migration).

Expose these REST endpoints:
  POST   /api/tasks          — create and queue a task, returns { task_id, status }
  GET    /api/tasks          — list all tasks
  GET    /api/tasks/{id}     — get single task with all steps
  DELETE /api/tasks/{id}     — remove task

### 2b. WebSocket Real-time Streaming

Create a WebSocket endpoint:
  WS /ws/{client_id}

On connect: send { event: "connected", client_id }
On each agent step: send { event: "step", task_id, type, message, tool?, timestamp }
On task status change: send { event: "task_update", task: Task }
Handle ping/pong keepalive: client sends { type: "ping" }, server replies { event: "pong" }
Handle disconnects gracefully — do not crash if client drops mid-task.

### 2c. Research Agent — Agentic Loop (BOTH Claude and Kimi)

Replace the existing single API call with a proper agentic loop for BOTH providers.

#### Claude API — Research Agent

```python
# Tool definition
tools = [
    {
        "type": "web_search_20250305",
        "name": "web_search"
    }
]

# Agentic loop
messages = [{"role": "user", "content": query}]

while iterations < MAX_ITERATIONS:
    response = await call_claude_api(messages, tools)
    
    # STOP SIGNAL: stop_reason == "end_turn"
    if response.stop_reason == "end_turn":
        final_text = extract_text(response.content)
        break
    
    # TOOL USE: stop_reason == "tool_use"  
    if response.stop_reason == "tool_use":
        messages.append({"role": "assistant", "content": response.content})
        
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                await broadcast_step(task_id, "tool_call", f'Searching: "{block.input.query}"')
                
                # TOOL RESULT ROLE: must be "user" with type "tool_result"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Search executed by Claude."   # Claude handles search server-side
                })
                
                await broadcast_step(task_id, "tool_result", f'Results received for: "{block.input.query}"')
        
        # Append tool results as a user turn
        messages.append({"role": "user", "content": tool_results})
```

#### Kimi API — Research Agent

```python
# Tool definition — Kimi uses builtin function format
tools = [
    {
        "type": "function",
        "function": {
            "name": "$web_search",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    }
]

# Agentic loop
messages = [{"role": "user", "content": query}]

while iterations < MAX_ITERATIONS:
    response = await call_kimi_api(messages, tools)
    choice = response.choices[0]
    
    # STOP SIGNAL: finish_reason == "stop"
    if choice.finish_reason == "stop":
        final_text = choice.message.content
        break
    
    # TOOL USE: check tool_calls on the message
    if choice.message.tool_calls:
        messages.append(choice.message)   # append assistant message with tool_calls
        
        for tool_call in choice.message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            await broadcast_step(task_id, "tool_call", f'Kimi searching: "{args["query"]}"')
            
            # TOOL RESULT ROLE: must be "tool" with tool_call_id
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f'Web search executed for: "{args["query"]}". Results available.'
            })
            
            await broadcast_step(task_id, "tool_result", f'Kimi got results for: "{args["query"]}"')
```

Use a model selector: if the Mezzofy AI config already has a preferred provider flag,
respect it. Otherwise default to Claude. Kimi is used when KIMI_API_KEY is set and 
the request specifies provider="kimi".

MAX_ITERATIONS = 8 for both. Broadcast each step in real-time via WebSocket.

### 2d. Developer Agent — Claude Code Headless

```python
async def run_developer_agent(task_id, query, client_id, work_dir=None):
    work_dir = work_dir or os.path.expanduser("~/mezzofy-workspace")
    os.makedirs(work_dir, exist_ok=True)
    
    cmd = [
        "claude",
        "--output-format", "stream-json",   # structured JSON stream
        "--no-interactive",                  # headless / background mode
        "-p", query                          # prompt
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=work_dir,
        env={**os.environ, "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY}
    )
    
    # Stream each JSON line from Claude Code stdout
    async for raw_line in process.stdout:
        line = raw_line.decode().strip()
        if not line:
            continue
        
        event = json.loads(line)
        event_type = event.get("type")
        
        if event_type == "assistant":
            # Claude Code reasoning text
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    await broadcast_step(task_id, client_id, "thinking", block["text"][:300])
        
        elif event_type == "tool_use":
            tool_name = event.get("name", "")
            tool_input = json.dumps(event.get("input", {}))[:150]
            await broadcast_step(task_id, client_id, "tool_call", f"{tool_name}: {tool_input}", tool=tool_name)
        
        elif event_type == "tool_result":
            content = str(event.get("content", ""))[:200]
            await broadcast_step(task_id, client_id, "tool_result", content)
        
        elif event_type == "result":
            await broadcast_step(task_id, client_id, "done", event.get("result", ""))
        
        elif event_type == "error":
            await broadcast_step(task_id, client_id, "error", event.get("error", ""))
    
    await process.wait()
```

---

## STEP 3 — FRONTEND: AGENT DASHBOARD

Extend the existing chat UI — do NOT replace it. Add an Agent Dashboard view
that can be toggled from the existing UI (tab, sidebar link, or modal — 
use whichever pattern matches the existing navigation in the project).

The Agent Dashboard must include:

### Task Dispatch Panel
- Dropdown or toggle to select agent: Research | Developer
- Text area for query input
- For Developer agent: optional working directory input field
- For Research agent: provider selector (Claude | Kimi) if both keys are configured
- Submit button — dispatches POST /api/tasks

### Real-time Task Queue
- Live list of all tasks (queued, running, done, failed)
- Each task shows: agent type, status indicator (colored dot), query preview, task ID
- Expandable task card showing:
  - Step-by-step log with icons per step type
  - Final result when done
  - Error message when failed

### WebSocket Connection
Replace any existing polling or one-shot fetch with a persistent WebSocket:

```javascript
const clientId = `client_${Math.random().toString(36).slice(2, 8)}`;
const ws = new WebSocket(`ws://YOUR_SERVER/ws/${clientId}`);

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  
  if (msg.event === "step") {
    // append to step log for msg.task_id
  }
  
  if (msg.event === "task_update") {
    // update task status in task list
  }
};

// Keepalive
setInterval(() => ws.readyState === 1 && ws.send(JSON.stringify({ type: "ping" })), 20000);

// Reconnect on disconnect
ws.onclose = () => setTimeout(() => reconnect(), 3000);
```

Preserve the existing single-turn chat UI for users who don't need the agent queue.
The agent dashboard is an added layer for power users / admin panel.

---

## STEP 4 — WIRING & INTEGRATION

1. The existing AI chat handler (whatever route currently handles user messages) 
   should be preserved AS-IS for backwards compatibility.

2. The new agent system uses /api/tasks + /ws/{client_id} as separate endpoints.

3. If the existing handler uses a single Claude or Kimi API call:
   - Extract it into a shared utility function
   - The new Research Agent uses this utility but wraps it in the agentic loop
   - The old handler can optionally be upgraded to call the agentic loop

4. Environment variables to support (add to .env.example or equivalent):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   KIMI_API_KEY=sk-...          # optional
   CLAUDE_MODEL=claude-sonnet-4-20250514
   KIMI_MODEL=moonshot-v1-8k
   MAX_AGENT_ITERATIONS=8
   AGENT_WORK_DIR=/home/ubuntu/mezzofy-workspace
   ```

---

## STEP 5 — FILES TO CREATE / MODIFY

Based on your audit in Step 1, determine exact file names. Suggested structure:

```
backend/
  agents/
    __init__.py
    base.py              # shared broadcast helpers, Task/Step models
    research_agent.py    # Claude + Kimi agentic loops
    developer_agent.py   # Claude Code headless subprocess
  routers/
    tasks.py             # POST/GET/DELETE /api/tasks
    websocket.py         # WS /ws/{client_id}
  [existing files — modify minimally]

frontend/
  components/
    AgentDashboard/
      index.jsx           # main dashboard component
      TaskCard.jsx        # expandable task card
      StepLog.jsx         # real-time step log
      AgentPanel.jsx      # dispatch form per agent
  hooks/
    useAgentWebSocket.js  # WebSocket hook with reconnect logic
  [existing files — add navigation link only]
```

Adapt this to the actual structure you find in the project.

---

## STEP 6 — QUALITY CHECKLIST

Before finishing, verify:

- [ ] Existing chat still works (no regression)
- [ ] Research Agent (Claude) — agentic loop runs, tool_call and tool_result steps broadcast
- [ ] Research Agent (Kimi) — $web_search tool_calls handled, role:"tool" results appended
- [ ] Developer Agent — Claude Code subprocess streams events, all event types handled
- [ ] WebSocket — connects, receives steps in real-time, reconnects on drop
- [ ] Background tasks — multiple tasks can run concurrently without blocking each other
- [ ] Task CRUD — create, list, get, delete all work
- [ ] Error handling — failed agent gracefully sets status:failed and broadcasts error step
- [ ] Env vars — all keys read from environment, never hardcoded
- [ ] CLAUDE.md conventions respected (check it before styling anything)

---

## CONSTRAINTS

- Python 3.10+ / FastAPI / asyncio — match existing backend stack
- Do not add new frontend frameworks — use whatever the project already uses
- Keep all new dependencies minimal — only add what is strictly necessary
- Install requirements: `pip install fastapi uvicorn httpx websockets`
- Claude Code must be installed on the server: `npm install -g @anthropic-ai/claude-code`
- Do not expose API keys to the frontend under any circumstances
- MAX_ITERATIONS cap is mandatory — never allow unbounded loops

---

## NOTES FOR CLAUDE CODE

- Run `find . -type f -name "*.py" | head -40` and `find . -type f -name "*.js" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" | head -40` first to map the codebase
- Read CLAUDE.md before writing any code
- Read the existing AI handler file fully before modifying it
- Comment all new functions with purpose, inputs, and outputs
- Add `# TODO: migrate to Redis` where in-memory storage is used
- Add `# TODO: add auth middleware` on all new API endpoints
- When in doubt about project conventions, match what already exists
