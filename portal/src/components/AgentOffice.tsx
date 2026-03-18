import React, { useRef, useEffect } from 'react'
import type { AgentStatus } from '../types'

interface Props {
  agents: AgentStatus[]
}

const AGENT_POSITIONS: Record<string, { x: number; y: number }> = {
  management: { x: 400, y: 60 },
  finance:    { x: 90,  y: 190 },
  sales:      { x: 210, y: 270 },
  hr:         { x: 330, y: 330 },
  marketing:  { x: 470, y: 330 },
  support:    { x: 590, y: 270 },
  research:   { x: 710, y: 190 },
  developer:  { x: 670, y: 330 },
  scheduler:  { x: 130, y: 320 },
}

const DEPT_COLORS: Record<string, string> = {
  finance:    '#FFB84D',
  sales:      '#00D4AA',
  marketing:  '#C77DFF',
  support:    '#4DA6FF',
  management: '#FF6B8A',
  hr:         '#DB2777',
  research:   '#4DA6FF',
  developer:  '#00D4AA',
  scheduler:  '#FFB84D',
}

const ALL_DEPTS = Object.keys(AGENT_POSITIONS)

function drawSprite(
  ctx: CanvasRenderingContext2D,
  dept: string,
  x: number,
  y: number,
  isBusy: boolean,
  bobOffset: number,
  tasksToday: number,
  activeTasks: number
) {
  const cy = y + bobOffset
  const scale = dept === 'management' ? 2.0 : 1.5

  // Desk
  ctx.fillStyle = '#1E3A5F'
  ctx.fillRect(x - 14 * scale, cy + 12 * scale, 28 * scale, 6 * scale)

  // Body color by department
  const bodyColors: Record<string, string> = {
    management: '#2D1B69',
    finance: '#064E3B',
    sales: '#1E3A5F',
    marketing: '#78350F',
    support: '#164E63',
    hr: '#4C1D95',
    research: '#1E3A5F',
    developer: '#064E3B',
    scheduler: '#78350F',
  }
  ctx.fillStyle = bodyColors[dept] || '#374151'
  ctx.fillRect(x - 6 * scale, cy + 2 * scale, 12 * scale, 10 * scale)

  // Head
  ctx.fillStyle = '#FBBF24'
  ctx.fillRect(x - 4 * scale, cy - 6 * scale, 8 * scale, 8 * scale)

  // Department-specific accessory
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
  }

  // Activity bubble with task count (orange circle above head)
  if (isBusy && activeTasks > 0) {
    const badgeX = x + 8 * scale
    const badgeY = cy - 16 * scale
    ctx.beginPath()
    ctx.arc(badgeX, badgeY, 8, 0, Math.PI * 2)
    ctx.fillStyle = '#f97316'
    ctx.fill()
    ctx.fillStyle = 'white'
    ctx.font = 'bold 9px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(String(activeTasks), badgeX, badgeY + 3)
    ctx.textAlign = 'left'
  } else if (isBusy) {
    const bubbleX = x + 10 * scale
    const bubbleY = cy - 16 * scale
    ctx.fillStyle = '#f97316'
    ctx.beginPath()
    // @ts-ignore - roundRect may not be in all TS lib versions
    ctx.roundRect(bubbleX, bubbleY, 24, 14, 4)
    ctx.fill()
    ctx.fillStyle = 'white'
    ctx.font = '8px monospace'
    ctx.fillText('...', bubbleX + 6, bubbleY + 10)
  }

  // Completed-today teal label below name area
  if (tasksToday > 0) {
    const labelY = cy + 72
    ctx.font = '9px monospace'
    ctx.fillStyle = '#00D4AA'
    ctx.textAlign = 'center'
    ctx.fillText(`\u2713${tasksToday}`, x, labelY)
    ctx.textAlign = 'left'
  }
}

export default function AgentOffice({ agents }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Build lookup from API agents
    const agentMap: Record<string, AgentStatus> = {}
    agents.forEach((a) => { agentMap[a.department] = a })

    const render = (timestamp: number) => {
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      // Checkerboard floor
      const tileSize = 40
      for (let row = 0; row < Math.ceil(H / tileSize); row++) {
        for (let col = 0; col < Math.ceil(W / tileSize); col++) {
          ctx.fillStyle = (row + col) % 2 === 0 ? '#1E2A3A' : '#162030'
          ctx.fillRect(col * tileSize, row * tileSize, tileSize, tileSize)
        }
      }

      // HKT clock — top-right
      const hkt = new Date().toLocaleString('en-HK', {
        timeZone: 'Asia/Hong_Kong',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        day: '2-digit', month: 'short', year: 'numeric'
      })
      ctx.font = '15px monospace'
      ctx.fillStyle = '#7A8FA6'
      ctx.textAlign = 'right'
      ctx.fillText(hkt + ' HKT', W - 10, 20)
      ctx.textAlign = 'left'

      // Draw each agent (all 9, even if not in API response)
      ALL_DEPTS.forEach((dept) => {
        const pos = AGENT_POSITIONS[dept]
        if (!pos) return
        const agent = agentMap[dept]
        const isBusy = agent?.is_busy || false
        const tasksToday = agent?.tasks_today || 0
        const activeTasks = isBusy ? 1 : 0
        const bobOffset = Math.sin(timestamp / 2000 + pos.x) * 2
        drawSprite(ctx, dept, pos.x, pos.y, isBusy, Math.round(bobOffset), tasksToday, activeTasks)
      })

      // Labels
      ctx.font = '14px Inter, sans-serif'
      ALL_DEPTS.forEach((dept) => {
        const pos = AGENT_POSITIONS[dept]
        if (!pos) return
        const agent = agentMap[dept]
        const label = agent?.name || dept.charAt(0).toUpperCase() + dept.slice(1)
        const deptColor = DEPT_COLORS[dept] || '#9CA3AF'
        const labelWidth = ctx.measureText(label).width
        ctx.fillStyle = 'rgba(0,0,0,0.6)'
        ctx.fillRect(pos.x - labelWidth / 2 - 4, pos.y + 26, labelWidth + 8, 14)
        ctx.fillStyle = agent?.is_busy ? deptColor : '#9CA3AF'
        ctx.fillText(label, pos.x - labelWidth / 2, pos.y + 37)
      })

      frameRef.current = requestAnimationFrame(render)
    }

    frameRef.current = requestAnimationFrame(render)
    return () => cancelAnimationFrame(frameRef.current)
  }, [agents])

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={480}
      className="w-full rounded-lg"
      style={{ imageRendering: 'pixelated', maxHeight: '480px' }}
    />
  )
}
