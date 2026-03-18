import React, { useRef, useEffect } from 'react'
import type { AgentStatus } from '../types'

interface Props {
  agents: AgentStatus[]
}

const AGENT_POSITIONS: Record<string, { x: number; y: number }> = {
  management: { x: 370, y: 80 },
  finance: { x: 100, y: 200 },
  sales: { x: 220, y: 260 },
  marketing: { x: 400, y: 260 },
  support: { x: 560, y: 200 },
  hr: { x: 660, y: 280 },
}

function drawSprite(
  ctx: CanvasRenderingContext2D,
  dept: string,
  x: number,
  y: number,
  isBusy: boolean,
  bobOffset: number
) {
  const cy = y + bobOffset
  const scale = dept === 'management' ? 1.5 : 1

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
  }
  ctx.fillStyle = bodyColors[dept] || '#374151'
  ctx.fillRect(x - 6 * scale, cy + 2 * scale, 12 * scale, 10 * scale)

  // Head
  ctx.fillStyle = '#FBBF24'
  ctx.fillRect(x - 4 * scale, cy - 6 * scale, 8 * scale, 8 * scale)

  // Department-specific accessory
  if (dept === 'management') {
    // Glasses
    ctx.fillStyle = '#6C63FF'
    ctx.fillRect(x - 5 * scale, cy - 4 * scale, 3 * scale, 2 * scale)
    ctx.fillRect(x + 2 * scale, cy - 4 * scale, 3 * scale, 2 * scale)
    // Purple tie
    ctx.fillStyle = '#7C3AED'
    ctx.fillRect(x - 1 * scale, cy + 2 * scale, 2 * scale, 6 * scale)
  } else if (dept === 'finance') {
    // Green visor
    ctx.fillStyle = '#059669'
    ctx.fillRect(x - 5 * scale, cy - 7 * scale, 10 * scale, 3 * scale)
  } else if (dept === 'sales') {
    // Headset
    ctx.fillStyle = '#60A5FA'
    ctx.fillRect(x - 5 * scale, cy - 5 * scale, 2 * scale, 4 * scale)
    ctx.fillRect(x + 3 * scale, cy - 5 * scale, 2 * scale, 4 * scale)
  } else if (dept === 'marketing') {
    // Orange beret
    ctx.fillStyle = '#F97316'
    ctx.fillRect(x - 5 * scale, cy - 8 * scale, 10 * scale, 3 * scale)
    ctx.fillRect(x + 3 * scale, cy - 7 * scale, 4 * scale, 2 * scale)
  } else if (dept === 'support') {
    // Teal headset
    ctx.fillStyle = '#0D9488'
    ctx.fillRect(x - 5 * scale, cy - 4 * scale, 2 * scale, 5 * scale)
    ctx.fillRect(x + 3 * scale, cy - 4 * scale, 2 * scale, 5 * scale)
  } else if (dept === 'hr') {
    // Pink folder
    ctx.fillStyle = '#DB2777'
    ctx.fillRect(x + 6 * scale, cy + 3 * scale, 6 * scale, 7 * scale)
  }

  // Busy speech bubble
  if (isBusy) {
    const bubbleX = x + 10 * scale
    const bubbleY = cy - 16 * scale
    ctx.fillStyle = '#6C63FF'
    ctx.beginPath()
    // @ts-ignore - roundRect may not be in all TS lib versions
    ctx.roundRect(bubbleX, bubbleY, 24, 14, 4)
    ctx.fill()
    ctx.fillStyle = 'white'
    ctx.font = '8px monospace'
    ctx.fillText('...', bubbleX + 6, bubbleY + 10)
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

      // Draw each agent
      agents.forEach((agent) => {
        const pos = AGENT_POSITIONS[agent.department]
        if (!pos) return
        const bobOffset = Math.sin(timestamp / 2000 + pos.x) * 2
        drawSprite(ctx, agent.department, pos.x, pos.y, agent.is_busy, Math.round(bobOffset))
      })

      // Labels
      ctx.font = '10px Inter, sans-serif'
      agents.forEach((agent) => {
        const pos = AGENT_POSITIONS[agent.department]
        if (!pos) return
        const label = agent.name
        const labelWidth = ctx.measureText(label).width
        ctx.fillStyle = 'rgba(0,0,0,0.6)'
        ctx.fillRect(pos.x - labelWidth / 2 - 4, pos.y + 26, labelWidth + 8, 14)
        ctx.fillStyle = agent.is_busy ? '#00D4AA' : '#9CA3AF'
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
      height={360}
      className="w-full rounded-lg"
      style={{ imageRendering: 'pixelated', maxHeight: '360px' }}
    />
  )
}
