import React, { useRef, useEffect } from 'react'
import type { AgentStatus } from '../types'

interface Props {
  agents: AgentStatus[]
  onAgentClick: (dept: string) => void
}

// ── Layout constants ─────────────────────────────────────────────────────────
const CANVAS_W = 900
const CANVAS_H = 520
const ROOM_X = 594   // Task Room starts here (left of divider wall)

// Agent home positions — left 2/3 zone, 3 rows
const HOME_POSITIONS: Record<string, { x: number; y: number }> = {
  // Row 0 — management (center, prominent)
  management: { x: 295, y: 95 },
  // Row 1 — 5 department agents
  finance:    { x: 55,  y: 215 },
  sales:      { x: 155, y: 215 },
  marketing:  { x: 255, y: 215 },
  support:    { x: 370, y: 215 },
  hr:         { x: 475, y: 215 },
  // Row 2 — 4 special agents
  legal:      { x: 80,  y: 355 },
  research:   { x: 190, y: 355 },
  developer:  { x: 305, y: 355 },
  scheduler:  { x: 420, y: 355 },
}

// Task Room meeting table seats (agents sit here when busy)
// Portrait table: TX=702, TY=168, TW=90, TH=240
// Left column seats (x ≈ 682), Right column seats (x ≈ 812)
const TABLE_SEATS = [
  { x: 682, y: 192 },   // left col, seat 1
  { x: 682, y: 240 },   // left col, seat 2
  { x: 682, y: 288 },   // left col, seat 3
  { x: 682, y: 336 },   // left col, seat 4
  { x: 682, y: 384 },   // left col, seat 5
  { x: 812, y: 192 },   // right col, seat 1
  { x: 812, y: 240 },   // right col, seat 2
  { x: 812, y: 288 },   // right col, seat 3
  { x: 812, y: 336 },   // right col, seat 4
  { x: 812, y: 384 },   // right col, seat 5
]

const DEPT_COLORS: Record<string, string> = {
  management: '#FF6B8A',
  finance:    '#FFB84D',
  sales:      '#00D4AA',
  marketing:  '#C77DFF',
  support:    '#4DA6FF',
  hr:         '#DB2777',
  legal:      '#F59E0B',
  research:   '#4DA6FF',
  developer:  '#00D4AA',
  scheduler:  '#FFB84D',
}

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

const ALL_DEPTS = Object.keys(HOME_POSITIONS)

// ── Sprite drawing ────────────────────────────────────────────────────────────
function drawSprite(
  ctx: CanvasRenderingContext2D,
  dept: string,
  x: number,
  y: number,
  isBusy: boolean,
  bobOffset: number,
  atTable: boolean,
) {
  const cy = y + bobOffset
  const scale = dept === 'management' ? 2.0 : 1.5

  // Desk — warm wood brown (visible against dark floor)
  ctx.fillStyle = atTable ? '#6B4E1A' : '#8B6530'
  ctx.fillRect(x - 16 * scale, cy + 12 * scale, 32 * scale, 7 * scale)
  // Desk edge highlight
  ctx.fillStyle = atTable ? '#9A6E2A' : '#A07840'
  ctx.fillRect(x - 16 * scale, cy + 12 * scale, 32 * scale, 2 * scale)

  // Body
  const bodyColors: Record<string, string> = {
    management: '#2D1B69', finance: '#064E3B', sales: '#1E3A5F',
    marketing: '#78350F', support: '#164E63', hr: '#4C1D95',
    legal: '#3B1A00', research: '#1E3A5F', developer: '#064E3B', scheduler: '#78350F',
  }
  ctx.fillStyle = bodyColors[dept] || '#374151'
  ctx.fillRect(x - 6 * scale, cy + 2 * scale, 12 * scale, 10 * scale)

  // Head
  ctx.fillStyle = '#FBBF24'
  ctx.fillRect(x - 4 * scale, cy - 6 * scale, 8 * scale, 8 * scale)

  // Dept accessory
  if (dept === 'management') {
    ctx.fillStyle = '#f97316'
    ctx.fillRect(x - 5 * scale, cy - 4 * scale, 3 * scale, 2 * scale)
    ctx.fillRect(x + 2 * scale, cy - 4 * scale, 3 * scale, 2 * scale)
    ctx.fillStyle = '#7C3AED'
    ctx.fillRect(x - 1 * scale, cy + 2 * scale, 2 * scale, 6 * scale)
  } else if (dept === 'finance') {
    ctx.fillStyle = '#059669'
    ctx.fillRect(x - 5 * scale, cy - 7 * scale, 10 * scale, 3 * scale)
  } else if (dept === 'sales') {
    ctx.fillStyle = '#60A5FA'
    ctx.fillRect(x - 5 * scale, cy - 5 * scale, 2 * scale, 4 * scale)
    ctx.fillRect(x + 3 * scale, cy - 5 * scale, 2 * scale, 4 * scale)
  } else if (dept === 'marketing') {
    ctx.fillStyle = '#F97316'
    ctx.fillRect(x - 5 * scale, cy - 8 * scale, 10 * scale, 3 * scale)
    ctx.fillRect(x + 3 * scale, cy - 7 * scale, 4 * scale, 2 * scale)
  } else if (dept === 'support') {
    ctx.fillStyle = '#0D9488'
    ctx.fillRect(x - 5 * scale, cy - 4 * scale, 2 * scale, 5 * scale)
    ctx.fillRect(x + 3 * scale, cy - 4 * scale, 2 * scale, 5 * scale)
  } else if (dept === 'hr') {
    ctx.fillStyle = '#DB2777'
    ctx.fillRect(x + 6 * scale, cy + 3 * scale, 6 * scale, 7 * scale)
  } else if (dept === 'research') {
    ctx.fillStyle = '#4DA6FF'
    ctx.fillRect(x - 5 * scale, cy - 7 * scale, 10 * scale, 2 * scale)
  } else if (dept === 'developer') {
    ctx.fillStyle = '#00D4AA'
    ctx.fillRect(x - 5 * scale, cy - 5 * scale, 10 * scale, 2 * scale)
  } else if (dept === 'scheduler') {
    ctx.fillStyle = '#FFB84D'
    ctx.fillRect(x - 5 * scale, cy - 7 * scale, 10 * scale, 3 * scale)
  } else if (dept === 'legal') {
    ctx.fillStyle = '#F59E0B'
    ctx.fillRect(x - 7 * scale, cy - 8 * scale, 14 * scale, 2 * scale)
    ctx.fillRect(x - 1 * scale, cy - 8 * scale, 2 * scale, 4 * scale)
    ctx.fillRect(x - 9 * scale, cy - 5 * scale, 5 * scale, 2 * scale)
    ctx.fillRect(x + 4 * scale, cy - 5 * scale, 5 * scale, 2 * scale)
    ctx.fillRect(x - 7 * scale, cy - 8 * scale, 1 * scale, 3 * scale)
    ctx.fillRect(x + 6 * scale, cy - 8 * scale, 1 * scale, 3 * scale)
  }
}

// ── Task Room ────────────────────────────────────────────────────────────────
function drawTaskRoom(ctx: CanvasRenderingContext2D, W: number, H: number, busyCount: number) {
  // Floor — warm checkerboard
  const tileS = 38
  for (let row = 0; row < Math.ceil(H / tileS); row++) {
    for (let col = 0; col < Math.ceil((W - ROOM_X) / tileS); col++) {
      ctx.fillStyle = (row + col) % 2 === 0 ? '#D8CFC0' : '#C8BFB0'
      ctx.fillRect(ROOM_X + col * tileS, row * tileS, tileS, tileS)
    }
  }

  // Wall divider (warm off-white strip)
  ctx.fillStyle = '#E8DCC8'
  ctx.fillRect(ROOM_X, 0, 5, H)

  // Room header band — white so black text is readable
  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.fillRect(ROOM_X + 5, 0, W - ROOM_X - 5, 56)

  // "TASK ROOM" label — black, centered
  const roomCenterX = ROOM_X + (W - ROOM_X) / 2
  ctx.font = 'bold 13px monospace'
  ctx.fillStyle = '#1A1200'
  ctx.textAlign = 'center'
  ctx.fillText('TASK ROOM', roomCenterX, 18)
  ctx.textAlign = 'left'

  // Busy indicator dot
  if (busyCount > 0) {
    ctx.beginPath()
    ctx.arc(ROOM_X + 20, 14, 5, 0, Math.PI * 2)
    ctx.fillStyle = '#f97316'
    ctx.fill()
  }

  // HKT Clock — centered in header, black text
  const hkt = new Date().toLocaleString('en-HK', {
    timeZone: 'Asia/Hong_Kong',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    day: '2-digit', month: 'short', year: 'numeric',
  })
  ctx.font = '10px monospace'
  ctx.fillStyle = '#3A2C10'
  ctx.textAlign = 'center'
  ctx.fillText(hkt + ' HKT', roomCenterX, 38)
  ctx.textAlign = 'left'

  // Meeting table — portrait orientation (rotated 90°), centered in Task Room
  const TX = 702, TY = 168, TW = 90, TH = 240
  ctx.fillStyle = '#5A3810'
  ctx.fillRect(TX, TY, TW, TH)
  ctx.fillStyle = '#7A5220'
  ctx.fillRect(TX, TY, TW, 6)           // top highlight
  ctx.fillStyle = '#4A2E0A'
  ctx.fillRect(TX + TW - 4, TY, 4, TH)  // right edge shadow
  // table legs
  ctx.fillStyle = '#3A2208'
  ctx.fillRect(TX - 8,       TY + 8,        8, 8)
  ctx.fillRect(TX - 8,       TY + TH - 16,  8, 8)
  ctx.fillRect(TX + TW,      TY + 8,        8, 8)
  ctx.fillRect(TX + TW,      TY + TH - 16,  8, 8)

  // Chairs — left column (5 chairs, spaced 48px apart vertically)
  for (let i = 0; i < 5; i++) {
    const cy = TY + 24 + i * 48
    ctx.fillStyle = '#1E3A5A'
    ctx.fillRect(TX - 34, cy - 11, 16, 22)   // seat
    ctx.fillRect(TX - 48, cy - 9,  14, 18)   // back
  }
  // Chairs — right column
  for (let i = 0; i < 5; i++) {
    const cy = TY + 24 + i * 48
    ctx.fillStyle = '#1E3A5A'
    ctx.fillRect(TX + TW + 18, cy - 11, 16, 22)   // seat
    ctx.fillRect(TX + TW + 34, cy - 9,  14, 18)   // back
  }

  // Session note at bottom
  if (busyCount > 0) {
    ctx.font = '10px monospace'
    ctx.fillStyle = '#f97316'
    ctx.textAlign = 'center'
    ctx.fillText(
      `● ${busyCount} agent${busyCount > 1 ? 's' : ''} in session`,
      ROOM_X + (W - ROOM_X) / 2,
      H - 14,
    )
    ctx.textAlign = 'left'
  }
}

// ── Label (dept + persona boxed) ─────────────────────────────────────────────
function drawLabel(
  ctx: CanvasRenderingContext2D,
  dept: string,
  x: number,
  y: number,
  deptColor: string,
  scale: number,
) {
  const persona = PERSONAS[dept] || dept
  const deptText = dept.toUpperCase()

  ctx.font = 'bold 11px monospace'
  const dw = ctx.measureText(deptText).width
  ctx.font = 'bold 12px sans-serif'
  const pw = ctx.measureText(persona).width

  const boxW = Math.max(dw, pw) + 22
  const boxH = 34
  const boxX = x - boxW / 2
  const boxY = y + 18 * scale

  ctx.beginPath()
  ctx.fillStyle = 'rgba(235,235,240,0.92)'
  ctx.strokeStyle = deptColor
  ctx.lineWidth = 1.5
  // @ts-ignore
  ctx.roundRect(boxX, boxY, boxW, boxH, 4)
  ctx.fill()
  ctx.stroke()

  ctx.font = 'bold 11px monospace'
  ctx.fillStyle = '#000000'
  ctx.textAlign = 'center'
  ctx.fillText(deptText, x, boxY + 13)

  ctx.font = 'bold 12px sans-serif'
  ctx.fillStyle = '#000000'
  ctx.fillText(persona, x, boxY + 28)
  ctx.textAlign = 'left'
}

// ── Status bubble for task room ───────────────────────────────────────────────
function drawStatusBubble(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  taskLabel: string | null,
  statusLabel: 'RUNNING' | 'QUEUING',
) {
  const isQueuing = statusLabel === 'QUEUING'
  const icon = isQueuing ? '\u23F3' : '\u25CF'
  const accentColor = isQueuing ? '#F59E0B' : '#f97316'
  const text1 = `${icon} ${statusLabel}`
  const raw = taskLabel || (isQueuing ? 'Waiting in queue...' : 'Working on task...')
  const text2 = raw.length > 20 ? raw.slice(0, 20) + '\u2026' : raw

  const bx = x - 52
  const by = y - 58
  const bw = 104
  const bh = 36

  ctx.fillStyle = 'rgba(5,8,18,0.92)'
  ctx.strokeStyle = accentColor
  ctx.lineWidth = 1.5
  // @ts-ignore
  ctx.roundRect(bx, by, bw, bh, 5)
  ctx.fill()
  ctx.stroke()

  // Bubble tail
  ctx.fillStyle = 'rgba(5,8,18,0.92)'
  ctx.beginPath()
  ctx.moveTo(x - 5, by + bh)
  ctx.lineTo(x,     by + bh + 9)
  ctx.lineTo(x + 5, by + bh)
  ctx.fill()
  ctx.strokeStyle = accentColor
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(x - 4, by + bh)
  ctx.lineTo(x,     by + bh + 8)
  ctx.lineTo(x + 4, by + bh)
  ctx.stroke()

  ctx.font = 'bold 8px monospace'
  ctx.fillStyle = accentColor
  ctx.textAlign = 'center'
  ctx.fillText(text1, x, by + 14)

  ctx.font = '8px monospace'
  ctx.fillStyle = '#9CA3AF'
  ctx.fillText(text2, x, by + 27)
  ctx.textAlign = 'left'
}

// ── Walking bubble ────────────────────────────────────────────────────────────
function drawWalkingBubble(ctx: CanvasRenderingContext2D, x: number, y: number, scale: number) {
  const bx = x + 6 * scale
  const by = y - 20 * scale
  ctx.fillStyle = '#f97316'
  ctx.beginPath()
  // @ts-ignore
  ctx.roundRect(bx, by, 26, 14, 4)
  ctx.fill()
  ctx.fillStyle = 'white'
  ctx.font = '8px monospace'
  ctx.fillText('...', bx + 7, by + 10)
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AgentOffice({ agents, onAgentClick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef<number>(0)
  const animPosRef = useRef<Record<string, { x: number; y: number }>>({})

  // Initialize animated positions once
  if (Object.keys(animPosRef.current).length === 0) {
    ALL_DEPTS.forEach((dept) => {
      const home = HOME_POSITIONS[dept]
      animPosRef.current[dept] = { x: home.x, y: home.y }
    })
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Click handler
    const handleClick = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      const scaleX = canvas.width / rect.width
      const scaleY = canvas.height / rect.height
      const cx = (e.clientX - rect.left) * scaleX
      const cy = (e.clientY - rect.top) * scaleY

      for (const dept of ALL_DEPTS) {
        const pos = animPosRef.current[dept]
        if (!pos) continue
        if (Math.abs(cx - pos.x) < 26 && Math.abs(cy - pos.y) < 26) {
          onAgentClick(dept)
          break
        }
      }
    }

    // Cursor — pointer when hovering agent
    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      const scaleX = canvas.width / rect.width
      const scaleY = canvas.height / rect.height
      const cx = (e.clientX - rect.left) * scaleX
      const cy = (e.clientY - rect.top) * scaleY
      const hit = ALL_DEPTS.some((dept) => {
        const pos = animPosRef.current[dept]
        return pos && Math.abs(cx - pos.x) < 26 && Math.abs(cy - pos.y) < 26
      })
      canvas.style.cursor = hit ? 'pointer' : 'default'
    }

    canvas.addEventListener('click', handleClick)
    canvas.addEventListener('mousemove', handleMouseMove)

    // Build agent lookup
    const agentMap: Record<string, AgentStatus> = {}
    agents.forEach((a) => { agentMap[a.department] = a })

    const render = (timestamp: number) => {
      const W = CANVAS_W
      const H = CANVAS_H
      ctx.clearRect(0, 0, W, H)

      // ── Left zone floor (dark checkerboard) ──────────────────────────────
      const tileS = 40
      for (let row = 0; row < Math.ceil(H / tileS); row++) {
        for (let col = 0; col < Math.ceil(ROOM_X / tileS); col++) {
          ctx.fillStyle = (row + col) % 2 === 0 ? '#1E2A3A' : '#162030'
          ctx.fillRect(col * tileS, row * tileS, tileS, tileS)
        }
      }

      // ── Task Room ─────────────────────────────────────────────────────────
      const busyDepts = ALL_DEPTS.filter((d) => agentMap[d]?.is_busy)
      drawTaskRoom(ctx, W, H, busyDepts.length)

      // ── Update animated positions (lerp) ──────────────────────────────────
      ALL_DEPTS.forEach((dept) => {
        const isBusy = agentMap[dept]?.is_busy || false
        let tx: number, ty: number

        if (isBusy) {
          const seatIdx = busyDepts.indexOf(dept) % TABLE_SEATS.length
          tx = TABLE_SEATS[seatIdx].x
          ty = TABLE_SEATS[seatIdx].y
        } else {
          tx = HOME_POSITIONS[dept].x
          ty = HOME_POSITIONS[dept].y
        }

        const cur = animPosRef.current[dept]
        cur.x += (tx - cur.x) * 0.07
        cur.y += (ty - cur.y) * 0.07
      })

      // ── Render all agents ────────────────────────────────────────────
      ALL_DEPTS.forEach((dept) => {
        const cur = animPosRef.current[dept]
        const home = HOME_POSITIONS[dept]
        const isBusy = agentMap[dept]?.is_busy || false
        const deptColor = DEPT_COLORS[dept] || '#9CA3AF'
        const scale = dept === 'management' ? 2.0 : 1.5

        const target = isBusy
          ? TABLE_SEATS[busyDepts.indexOf(dept) % TABLE_SEATS.length]
          : home
        const distToTarget = Math.hypot(cur.x - target.x, cur.y - target.y)
        const isWalking = distToTarget > 8
        const atTable = cur.x > ROOM_X - 30

        const bobSpeed = isWalking ? 600 : 2000
        const bobAmp = isWalking ? 3 : 2
        const bobOffset = Math.round(Math.sin(timestamp / bobSpeed + home.x) * bobAmp)

        drawSprite(ctx, dept, cur.x, cur.y, isBusy, bobOffset, atTable)

        if (atTable && isBusy) {
          const isQueued = agentMap[dept]?.current_status === 'queued'
          drawStatusBubble(
            ctx,
            cur.x,
            cur.y,
            agentMap[dept]?.current_task || null,
            isQueued ? 'QUEUING' : 'RUNNING',
          )
        } else if (isWalking) {
          drawWalkingBubble(ctx, cur.x, cur.y, scale)
        }

        drawLabel(ctx, dept, cur.x, cur.y + bobOffset, deptColor, scale)
      })

      frameRef.current = requestAnimationFrame(render)
    }

    frameRef.current = requestAnimationFrame(render)

    return () => {
      cancelAnimationFrame(frameRef.current)
      canvas.removeEventListener('click', handleClick)
      canvas.removeEventListener('mousemove', handleMouseMove)
    }
  }, [agents, onAgentClick])

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_W}
      height={CANVAS_H}
      className="w-full rounded-lg"
      style={{ imageRendering: 'pixelated', maxHeight: `${CANVAS_H}px` }}
    />
  )
}
