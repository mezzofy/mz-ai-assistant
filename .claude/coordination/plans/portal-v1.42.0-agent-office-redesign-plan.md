# Plan: Mission Control Portal v1.42.0 — Agent Office Redesign
**Workflow:** change-request
**Date:** 2026-03-19
**Created by:** Lead Agent

---

## Overview

Three features requested for the Agent Office canvas on the Dashboard:

| # | Feature | Complexity |
|---|---------|-----------|
| 1a | Agent label: dept name + persona name boxed together | Low |
| 1b | Click agent sprite → chat dialog popup | High |
| 1c | Task Room (right 1/3), agents in left 2/3 with desks + computers, busy agents walk to Task Room | Very High |

**Files to modify:**
- `portal/src/components/AgentOffice.tsx` — full canvas redesign
- `portal/src/components/AgentChatDialog.tsx` — NEW component
- `portal/src/pages/DashboardPage.tsx` — wire dialog + chat state
- `portal/src/api/portal.ts` — add `sendAgentMessage()` API call
- `portal/src/types/index.ts` — extend `AgentStatus` with `current_task_status?`

---

## Layout Design

### Canvas Dimensions: 900 × 520

```
┌──────────────────────────────────────────────────────────┬──────────────────┐
│                                                          │  TASK ROOM       │
│              AGENT WORK ZONE (left 66%)                  │  (right 34%)     │
│                   x: 0 → 590                             │  x: 590 → 900    │
│                                                          │                  │
│   Row 0 (y=90):   [Max/Mgmt]  (center, larger)          │  ┌────────────┐  │
│                                                          │  │  MEETING   │  │
│   Row 1 (y=210):  [Fiona] [Sam] [Maya] [Suki] [Hana]    │  │   TABLE    │  │
│                                                          │  │  ══════════│  │
│   Row 2 (y=350):  [Leo] [Rex] [Dev] [Sched]             │  └────────────┘  │
│                                                          │                  │
│   Each agent: desk + computer monitor + pixel sprite     │  Busy agents sit │
│                                                          │  here w/ bubble  │
└──────────────────────────────────────────────────────────┴──────────────────┘
```

### Agent Desk Positions (Home / Idle positions, LEFT ZONE)

```typescript
const HOME_POSITIONS: Record<string, { x: number; y: number }> = {
  management: { x: 295, y: 90  },   // Row 0 center — larger scale (2.0)
  finance:    { x: 60,  y: 210 },   // Row 1
  sales:      { x: 165, y: 210 },
  marketing:  { x: 270, y: 210 },
  support:    { x: 375, y: 210 },
  hr:         { x: 480, y: 210 },
  legal:      { x: 80,  y: 350 },   // Row 2
  research:   { x: 190, y: 350 },
  developer:  { x: 300, y: 350 },
  scheduler:  { x: 410, y: 350 },
}
```

### Task Room Layout (x=590 to x=900)

```
- Room background: dark navy with lighter wall feel — rgba(30,40,60,0.95)
- Left wall border: vertical line x=590, color '#E8E0D0', width 3px
- Room label: "TASK ROOM" centered at x=745, y=28 (bold, white)
- Clock: x=890, y=50 (right-aligned HKT)
- Meeting table: fillRect(610, 160, 275, 90) color '#8B6914' (dark wood)
  - Table highlight (top edge): y=160, h=4, lighter '#C4953A'
  - Table legs: thin rects at corners
- Chairs top row: y≈145, x positions: 630, 680, 730, 780, 830
- Chairs bottom row: y≈258, same x positions
```

### Task Room Seats (where busy agents sit)

```typescript
const TABLE_SEATS: Array<{ x: number; y: number; side: 'top' | 'bottom' }> = [
  { x: 635, y: 145, side: 'top'    },
  { x: 690, y: 145, side: 'top'    },
  { x: 745, y: 145, side: 'top'    },
  { x: 800, y: 145, side: 'top'    },
  { x: 855, y: 145, side: 'top'    },
  { x: 635, y: 265, side: 'bottom' },
  { x: 690, y: 265, side: 'bottom' },
  { x: 745, y: 265, side: 'bottom' },
  { x: 800, y: 265, side: 'bottom' },
  { x: 855, y: 265, side: 'bottom' },
]
```

---

## Feature 1a — Agent Labels (Dept + Persona, Boxed)

**Current:** Single-row label showing agent name only, drawn as text with dark background rect.

**New:** Two-row boxed label drawn BELOW each sprite (whether at desk or table):

```
┌──────────────┐
│  MANAGEMENT  │  ← dept name, 9px, dept color
│     Max      │  ← persona name, 11px bold, white
└──────────────┘
```

**Implementation:**
```
// After drawing sprite at (x, cy):
const deptLabel = dept.toUpperCase()
const personaLabel = PERSONAS[dept] || dept

// Measure widths
ctx.font = '9px monospace'
const deptW = ctx.measureText(deptLabel).width
ctx.font = 'bold 11px Inter, sans-serif'
const personaW = ctx.measureText(personaLabel).width
const boxW = Math.max(deptW, personaW) + 16
const boxH = 28
const boxX = x - boxW / 2
const boxY = cy + 30 * scale   // below desk

// Draw box
ctx.fillStyle = 'rgba(0,0,0,0.75)'
ctx.strokeStyle = deptColor
ctx.lineWidth = 1
ctx.beginPath()
ctx.roundRect(boxX, boxY, boxW, boxH, 4)
ctx.fill()
ctx.stroke()

// Dept name (top)
ctx.font = '9px monospace'
ctx.fillStyle = deptColor
ctx.textAlign = 'center'
ctx.fillText(deptLabel, x, boxY + 11)

// Persona name (bottom)
ctx.font = 'bold 11px Inter, sans-serif'
ctx.fillStyle = '#FFFFFF'
ctx.fillText(personaLabel, x, boxY + 24)
ctx.textAlign = 'left'
```

---

## Feature 1b — Click to Chat

**Architecture:**
- `AgentOffice` fires `onAgentClick(dept: string)` prop callback on canvas click
- `DashboardPage` manages `selectedChatDept: string | null` state
- `DashboardPage` renders `<AgentChatDialog />` as absolute-overlay modal
- Click detection uses `animatedPositionsRef` (see feature 1c)

### Click Detection in AgentOffice

Add `onAgentClick` to props interface:
```typescript
interface Props {
  agents: AgentStatus[]
  onAgentClick: (dept: string) => void
}
```

In `useEffect`, add canvas click event listener (inside the effect, after canvas ref is set):
```typescript
const handleClick = (e: MouseEvent) => {
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  const cx = (e.clientX - rect.left) * scaleX
  const cy = (e.clientY - rect.top) * scaleY

  for (const dept of ALL_DEPTS) {
    const pos = animPosRef.current[dept]
    if (!pos) continue
    const hitRadius = 28  // click area around sprite center
    const dx = Math.abs(cx - pos.x)
    const dy = Math.abs(cy - pos.y)
    if (dx < hitRadius && dy < hitRadius) {
      onAgentClick(dept)
      break
    }
  }
}
canvas.addEventListener('click', handleClick)
// cleanup: canvas.removeEventListener('click', handleClick)
```

Also set `canvas.style.cursor = 'pointer'` on mousemove when hovering over sprite (optional enhancement).

### AgentChatDialog Component (NEW FILE)

**`portal/src/components/AgentChatDialog.tsx`**

```typescript
interface Props {
  dept: string
  onClose: () => void
}

interface Message {
  role: 'user' | 'agent'
  content: string
  timestamp: Date
}
```

**UI design:**
```
┌─────────────────────────────────────────────────┐
│ 🟢  Leo  (Legal Agent)              [×] Close   │  ← header, dept color accent
├─────────────────────────────────────────────────┤
│                                                  │
│   ← agent bubble: "Hi! I'm Leo, how can I..."  │  ← welcome message on open
│                                                  │
│          user bubble: "Review this NDA" →       │
│                                                  │
│   ← agent bubble: "Sure! Let me analyze..."    │
│                                                  │
│                                                  │
├─────────────────────────────────────────────────┤
│  [Message input field...]          [Send ▶]     │
└─────────────────────────────────────────────────┘
```

**Positioning:** Fixed overlay, centered, z-50:
```css
position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
width: 480px; height: 560px; z-index: 50;
background: #0F1623; border: 1px solid #1E2A3A; border-radius: 12px;
```

Backdrop: `position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 49`

**Chat API call:**
```typescript
const sendMessage = async () => {
  if (!inputText.trim() || sending) return
  const userMsg = inputText.trim()
  setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: new Date() }])
  setInputText('')
  setSending(true)
  try {
    const res = await portalApi.sendAgentMessage(dept, userMsg, sessionIdRef.current)
    const reply = res.data.reply || res.data.message || 'Task received.'
    if (res.data.session_id) sessionIdRef.current = res.data.session_id
    setMessages(prev => [...prev, { role: 'agent', content: reply, timestamp: new Date() }])
  } catch {
    setMessages(prev => [...prev, { role: 'agent', content: '⚠ Connection error. Please try again.', timestamp: new Date() }])
  } finally {
    setSending(false)
  }
}
```

`sessionIdRef` — `useRef<string>(crypto.randomUUID())` — maintains session per dialog open.

**Welcome message:** On mount, push a canned greeting:
```typescript
useEffect(() => {
  const greetings: Record<string, string> = {
    management: "Hi, I'm Max. Ready to pull your cross-department KPIs.",
    finance:    "Hi, I'm Fiona. I can generate financial reports or analyze revenue.",
    sales:      "Hi, I'm Sam. Need help with leads, outreach, or pitch decks?",
    marketing:  "Hi, I'm Maya. Let's create some great marketing content.",
    support:    "Hi, I'm Suki. I can check tickets, SLAs, and send customer comms.",
    hr:         "Hi, I'm Hana. Ask me about headcount, leave, or HR reports.",
    legal:      "Hi, I'm Leo. I can review contracts, draft NDAs, or advise on jurisdiction.",
    research:   "Hi, I'm Rex. Give me a research topic and I'll dig in.",
    developer:  "Hi, I'm Dev. Need code written, reviewed, or debugged?",
    scheduler:  "Hi, I'm Sched. Tell me what to schedule — I'll handle the cron.",
  }
  setMessages([{ role: 'agent', content: greetings[dept] || 'Hello! How can I help?', timestamp: new Date() }])
}, [dept])
```

---

## Feature 1c — Task Room + Agent Walk Animation

### New Canvas Architecture

The `render()` loop now handles:
1. Draw checkerboard floor (left zone only, x < 590)
2. Draw Task Room background (right zone, x ≥ 590)
3. Draw computer monitors at each home desk
4. Update `animPosRef` — lerp each agent toward target position
5. Draw sprites at animated positions
6. Draw agent labels (feature 1a)
7. Draw status bubbles for task-room agents

### Animated Positions

```typescript
const animPosRef = useRef<Record<string, { x: number; y: number }>>({})

// Initialize on first render (run once):
if (Object.keys(animPosRef.current).length === 0) {
  ALL_DEPTS.forEach(dept => {
    const home = HOME_POSITIONS[dept]
    animPosRef.current[dept] = { x: home.x, y: home.y }
  })
}
```

In render loop, BEFORE drawing sprites:
```typescript
// Determine busy agents and assign table seats
const busyDepts = ALL_DEPTS.filter(d => agentMap[d]?.is_busy)

ALL_DEPTS.forEach((dept) => {
  const isBusy = agentMap[dept]?.is_busy || false
  let targetX: number, targetY: number

  if (isBusy) {
    const seatIdx = busyDepts.indexOf(dept) % TABLE_SEATS.length
    targetX = TABLE_SEATS[seatIdx].x
    targetY = TABLE_SEATS[seatIdx].y
  } else {
    targetX = HOME_POSITIONS[dept].x
    targetY = HOME_POSITIONS[dept].y
  }

  // Lerp toward target (smooth walk)
  const cur = animPosRef.current[dept]
  cur.x += (targetX - cur.x) * 0.06
  cur.y += (targetY - cur.y) * 0.06
})
```

### Task Room Rendering

Draw Task Room BEFORE agents (so agents render on top):

```typescript
// Task Room walls
const ROOM_X = 590
ctx.fillStyle = '#0D1520'  // slightly different dark shade for room floor
ctx.fillRect(ROOM_X, 0, W - ROOM_X, H)

// Left wall border (white strip)
ctx.fillStyle = '#D4C9A8'   // warm off-white wall
ctx.fillRect(ROOM_X, 0, 4, H)

// Task Room floor — lighter checkerboard (cream/tan)
const tileS = 40
for (let row = 0; row < Math.ceil(H / tileS); row++) {
  for (let col = 0; col < Math.ceil((W - ROOM_X) / tileS); col++) {
    const rx = ROOM_X + col * tileS
    ctx.fillStyle = (row + col) % 2 === 0 ? '#E8E0D0' : '#D8CFC0'
    ctx.fillRect(rx, row * tileS, tileS, tileS)
  }
}

// Room label
ctx.font = 'bold 13px monospace'
ctx.fillStyle = '#1A1200'
ctx.textAlign = 'center'
ctx.fillText('TASK ROOM', ROOM_X + (W - ROOM_X) / 2, 22)
ctx.textAlign = 'left'

// Clock (right-aligned, inside task room)
const hkt = new Date().toLocaleString('en-HK', { ... })
ctx.font = '11px monospace'
ctx.fillStyle = '#5A4A30'
ctx.textAlign = 'right'
ctx.fillText(hkt + ' HKT', W - 8, 40)
ctx.textAlign = 'left'

// Meeting table (dark wood)
const TABLE_X = ROOM_X + 20, TABLE_Y = 155, TABLE_W = 270, TABLE_H = 100
ctx.fillStyle = '#6B4E1A'  // dark mahogany
ctx.fillRect(TABLE_X, TABLE_Y, TABLE_W, TABLE_H)
ctx.fillStyle = '#8B6924'  // highlight
ctx.fillRect(TABLE_X, TABLE_Y, TABLE_W, 6)
ctx.fillStyle = '#5A3E12'  // shadow edge
ctx.fillRect(TABLE_X, TABLE_Y + TABLE_H - 4, TABLE_W, 4)

// Table legs
ctx.fillStyle = '#4A3210'
ctx.fillRect(TABLE_X + 10, TABLE_Y + TABLE_H, 8, 15)
ctx.fillRect(TABLE_X + TABLE_W - 18, TABLE_Y + TABLE_H, 8, 15)

// Chairs top row (5 chairs above table)
for (let i = 0; i < 5; i++) {
  const cx = TABLE_X + 20 + i * 55
  ctx.fillStyle = '#2A4A6A'  // dark blue chair
  ctx.fillRect(cx - 10, TABLE_Y - 18, 20, 14)   // seat
  ctx.fillRect(cx - 8, TABLE_Y - 30, 16, 12)    // back
}

// Chairs bottom row
for (let i = 0; i < 5; i++) {
  const cx = TABLE_X + 20 + i * 55
  ctx.fillStyle = '#2A4A6A'
  ctx.fillRect(cx - 10, TABLE_Y + TABLE_H + 4, 20, 14)   // seat
  ctx.fillRect(cx - 8, TABLE_Y + TABLE_H + 18, 16, 12)   // back
}

// "Meeting in progress" label if any agent is busy
if (busyDepts.length > 0) {
  ctx.font = '10px monospace'
  ctx.fillStyle = '#f97316'
  ctx.textAlign = 'center'
  ctx.fillText(`● ${busyDepts.length} agent${busyDepts.length > 1 ? 's' : ''} in session`, ROOM_X + (W - ROOM_X) / 2, H - 15)
  ctx.textAlign = 'left'
}
```

### Computer Monitor at Each Home Desk

Add to `drawSprite()` — draw monitor BEFORE body/head (so body overlaps stand):

```typescript
// Computer monitor (drawn at home position, scaled)
if (!isBusy) {   // only show monitor when at desk
  const monScale = dept === 'management' ? 2.0 : 1.5
  // Screen
  ctx.fillStyle = '#0A1628'   // dark monitor frame
  ctx.fillRect(x - 10 * monScale, cy - 28 * monScale, 20 * monScale, 14 * monScale)
  // Screen glow (green/cyan — active display)
  ctx.fillStyle = '#0A3A2A'
  ctx.fillRect(x - 9 * monScale, cy - 27 * monScale, 18 * monScale, 12 * monScale)
  // Screen content (tiny colored lines = code/data)
  ctx.fillStyle = '#00D4AA'
  ctx.fillRect(x - 7 * monScale, cy - 25 * monScale, 10 * monScale, 1 * monScale)
  ctx.fillRect(x - 7 * monScale, cy - 23 * monScale, 7 * monScale, 1 * monScale)
  ctx.fillRect(x - 7 * monScale, cy - 21 * monScale, 9 * monScale, 1 * monScale)
  // Monitor stand
  ctx.fillStyle = '#374151'
  ctx.fillRect(x - 2 * monScale, cy - 14 * monScale, 4 * monScale, 4 * monScale)
  ctx.fillRect(x - 5 * monScale, cy - 11 * monScale, 10 * monScale, 2 * monScale)
}
```

### Status Bubble for Task Room Agents

Replace the existing orange activity bubble (which shows above sprite) with a more detailed speech-bubble style when agent is in Task Room:

```typescript
// When agent is near table (x > 580):
if (isBusy && currentPos.x > 580) {
  const taskLabel = agentMap[dept]?.current_task || 'Running task...'
  const statusText = '● RUNNING'
  const truncated = taskLabel.length > 22 ? taskLabel.slice(0, 22) + '…' : taskLabel

  // Speech bubble
  const bx = currentPos.x - 50
  const by = currentPos.y - 55
  const bw = 100
  const bh = 34

  ctx.fillStyle = 'rgba(0,0,0,0.85)'
  ctx.strokeStyle = '#f97316'
  ctx.lineWidth = 1.5
  // @ts-ignore
  ctx.roundRect(bx, by, bw, bh, 5)
  ctx.fill()
  ctx.stroke()

  // Bubble tail
  ctx.fillStyle = 'rgba(0,0,0,0.85)'
  ctx.beginPath()
  ctx.moveTo(currentPos.x - 4, by + bh)
  ctx.lineTo(currentPos.x, by + bh + 8)
  ctx.lineTo(currentPos.x + 4, by + bh)
  ctx.fill()

  // Status text
  ctx.font = 'bold 8px monospace'
  ctx.fillStyle = '#f97316'
  ctx.textAlign = 'center'
  ctx.fillText(statusText, currentPos.x, by + 13)
  ctx.font = '8px monospace'
  ctx.fillStyle = '#9CA3AF'
  ctx.fillText(truncated, currentPos.x, by + 25)
  ctx.textAlign = 'left'
}
```

When agent is WALKING (between desk and table — detected by checking distance to target > 8px):
- Show a small orange `...` bubble above head (existing behavior)
- Add a simple "walk cycle": draw slightly offset body each frame

---

## Portal API Addition

### `portal/src/api/portal.ts` — Add `sendAgentMessage`

```typescript
sendAgentMessage: (dept: string, message: string, sessionId: string) =>
  client.post('/chat/send', {
    message,
    department: dept,
    session_id: sessionId,
  }),
```

---

## DashboardPage Updates

### New state:
```typescript
const [chatDept, setChatDept] = useState<string | null>(null)
```

### AgentOffice — add onAgentClick:
```tsx
<AgentOffice agents={agentList} onAgentClick={(dept) => setChatDept(dept)} />
```

### AgentChatDialog — render when chatDept is set:
```tsx
{chatDept && (
  <AgentChatDialog
    dept={chatDept}
    onClose={() => setChatDept(null)}
  />
)}
```

### Import AgentChatDialog at top of DashboardPage.

---

## Persona Lookup (in AgentOffice + AgentChatDialog)

```typescript
const PERSONAS: Record<string, string> = {
  management: 'Max',
  finance:    'Fiona',
  sales:      'Sam',
  marketing:  'Maya',
  support:    'Suki',
  hr:         'Hana',
  legal:      'Leo',
  research:   'Rex',
  developer:  'Dev',
  scheduler:  'Sched',
}
```

---

## Files Modified

| File | Type | Change |
|------|------|--------|
| `portal/src/components/AgentOffice.tsx` | MODIFY | Full redesign — layout, Task Room, walk animation, labels, click detection |
| `portal/src/components/AgentChatDialog.tsx` | NEW | Chat dialog modal |
| `portal/src/pages/DashboardPage.tsx` | MODIFY | Add chatDept state, render dialog, pass onAgentClick |
| `portal/src/api/portal.ts` | MODIFY | Add `sendAgentMessage()` |

---

## Session Estimate: 1 Frontend session (large — ~50% context)

### Implementation Order (single session):

1. `portal.ts` — add `sendAgentMessage` (2 min)
2. `AgentOffice.tsx` — full redesign:
   a. Add HOME_POSITIONS, TABLE_SEATS, PERSONAS constants
   b. Add `animPosRef`, `onAgentClick` prop
   c. Rewrite render() — floor split, Task Room, monitors, walk lerp, labels, bubbles
   d. Add click event listener
3. `AgentChatDialog.tsx` — new component (chat UI)
4. `DashboardPage.tsx` — chatDept state + dialog render

### Quality Gate (Lead reviews):
- [ ] Canvas shows left 2/3 agent zone + right 1/3 Task Room with different floor
- [ ] White/warm wall border visible at x=590 separating zones
- [ ] Meeting table with chairs visible in Task Room
- [ ] All 10 agent sprites visible at their home desks with computer monitors
- [ ] Each agent has dept+persona label box below them
- [ ] Management sprite is larger (scale 2.0)
- [ ] Clicking an agent sprite opens chat dialog
- [ ] Chat dialog shows persona greeting on open
- [ ] Sending a message calls `/chat/send` with correct dept
- [ ] When `is_busy` is true, agent animates toward Task Room seat (smooth lerp)
- [ ] Status bubble shown over task-room agents: "● RUNNING" + task name
- [ ] Walking agents show `...` bubble mid-walk
- [ ] Clock moved to inside Task Room header area
- [ ] No regressions on other dashboard panels

---

## Delegation

**Frontend Agent only** — single agent, all 4 files.

This is complex — approximately 250–350 lines of new/replaced code. Estimated 45–55% context usage for Frontend Agent.
