import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'

function AIIllustration() {
  return (
    <svg viewBox="0 0 500 600" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      <style>{`
        @keyframes pulse {
          0%, 100% { r: 6; opacity: 0.9; }
          50% { r: 12; opacity: 0.3; }
        }
        @keyframes pulse-ring {
          0% { r: 8; opacity: 0.6; }
          100% { r: 24; opacity: 0; }
        }
        @keyframes node-glow {
          0%, 100% { opacity: 0.7; }
          50% { opacity: 1; }
        }
      `}</style>

      {/* Faint hexagonal grid */}
      {[
        { x: 80, y: 120 }, { x: 140, y: 120 }, { x: 200, y: 120 }, { x: 260, y: 120 }, { x: 320, y: 120 }, { x: 380, y: 120 },
        { x: 110, y: 170 }, { x: 170, y: 170 }, { x: 230, y: 170 }, { x: 290, y: 170 }, { x: 350, y: 170 }, { x: 410, y: 170 },
        { x: 80, y: 220 }, { x: 140, y: 220 }, { x: 200, y: 220 }, { x: 260, y: 220 }, { x: 320, y: 220 }, { x: 380, y: 220 },
        { x: 110, y: 270 }, { x: 170, y: 270 }, { x: 230, y: 270 }, { x: 290, y: 270 }, { x: 350, y: 270 }, { x: 410, y: 270 },
        { x: 80, y: 320 }, { x: 140, y: 320 }, { x: 200, y: 320 }, { x: 260, y: 320 }, { x: 320, y: 320 }, { x: 380, y: 320 },
        { x: 110, y: 370 }, { x: 170, y: 370 }, { x: 230, y: 370 }, { x: 290, y: 370 }, { x: 350, y: 370 }, { x: 410, y: 370 },
        { x: 80, y: 420 }, { x: 140, y: 420 }, { x: 200, y: 420 }, { x: 260, y: 420 }, { x: 320, y: 420 }, { x: 380, y: 420 },
        { x: 110, y: 470 }, { x: 170, y: 470 }, { x: 230, y: 470 }, { x: 290, y: 470 }, { x: 350, y: 470 }, { x: 410, y: 470 },
      ].map((h, i) => (
        <polygon
          key={`hex-${i}`}
          points={[0, 1, 2, 3, 4, 5].map(j => {
            const angle = (Math.PI / 3) * j - Math.PI / 6
            return `${h.x + 22 * Math.cos(angle)},${h.y + 22 * Math.sin(angle)}`
          }).join(' ')}
          fill="none"
          stroke="#1E3A5F"
          strokeWidth="0.5"
          opacity="0.4"
        />
      ))}

      {/* Connecting lines between nodes */}
      <line x1="130" y1="200" x2="250" y2="160" stroke="#f97316" strokeWidth="1" opacity="0.25" />
      <line x1="250" y1="160" x2="370" y2="230" stroke="#f97316" strokeWidth="1" opacity="0.2" />
      <line x1="370" y1="230" x2="320" y2="350" stroke="#00D4AA" strokeWidth="1" opacity="0.25" />
      <line x1="320" y1="350" x2="180" y2="380" stroke="#00D4AA" strokeWidth="1" opacity="0.2" />
      <line x1="180" y1="380" x2="130" y2="200" stroke="#f97316" strokeWidth="1" opacity="0.15" />
      <line x1="250" y1="160" x2="320" y2="350" stroke="#1E3A5F" strokeWidth="1" opacity="0.3" />
      <line x1="130" y1="200" x2="370" y2="230" stroke="#1E3A5F" strokeWidth="0.5" opacity="0.2" />
      <line x1="250" y1="160" x2="180" y2="380" stroke="#1E3A5F" strokeWidth="0.5" opacity="0.15" />
      <line x1="200" y1="480" x2="320" y2="350" stroke="#00D4AA" strokeWidth="1" opacity="0.2" />
      <line x1="200" y1="480" x2="180" y2="380" stroke="#f97316" strokeWidth="1" opacity="0.15" />
      <line x1="370" y1="230" x2="400" y2="420" stroke="#1E3A5F" strokeWidth="0.5" opacity="0.2" />
      <line x1="400" y1="420" x2="320" y2="350" stroke="#f97316" strokeWidth="1" opacity="0.15" />

      {/* Static nodes — orange */}
      <circle cx="250" cy="160" r="7" fill="#f97316" opacity="0.85" />
      <circle cx="370" cy="230" r="5" fill="#f97316" opacity="0.7" />
      <circle cx="400" cy="420" r="4" fill="#f97316" opacity="0.5" />

      {/* Static nodes — teal */}
      <circle cx="320" cy="350" r="6" fill="#00D4AA" opacity="0.8" />
      <circle cx="180" cy="380" r="5" fill="#00D4AA" opacity="0.6" />

      {/* Static nodes — semi-transparent */}
      <circle cx="130" cy="200" r="5" fill="#4DA6FF" opacity="0.4" />
      <circle cx="200" cy="480" r="4" fill="#4DA6FF" opacity="0.35" />
      <circle cx="290" cy="270" r="3" fill="#f97316" opacity="0.3" />

      {/* Pulsing nodes with animated rings */}
      <circle cx="250" cy="160" r="6" fill="none" stroke="#f97316" strokeWidth="1.5" opacity="0.6">
        <animate attributeName="r" values="8;24;8" dur="3s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.6;0;0.6" dur="3s" repeatCount="indefinite" />
      </circle>

      <circle cx="320" cy="350" r="6" fill="none" stroke="#00D4AA" strokeWidth="1.5" opacity="0.6">
        <animate attributeName="r" values="8;22;8" dur="2.5s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.5;0;0.5" dur="2.5s" repeatCount="indefinite" />
      </circle>

      <circle cx="180" cy="380" r="5" fill="none" stroke="#00D4AA" strokeWidth="1" opacity="0.5">
        <animate attributeName="r" values="7;20;7" dur="3.5s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.4;0;0.4" dur="3.5s" repeatCount="indefinite" />
      </circle>

      {/* MEZZOFY AI label */}
      <text
        x="250"
        y="70"
        textAnchor="middle"
        fontFamily="'Courier New', monospace"
        fontSize="18"
        fill="#7A8FA6"
        letterSpacing="4"
      >
        MEZZOFY AI
      </text>

      {/* Subtle subtitle */}
      <text
        x="250"
        y="92"
        textAnchor="middle"
        fontFamily="'Courier New', monospace"
        fontSize="10"
        fill="#3A5068"
        letterSpacing="2"
      >
        COMMAND CENTER
      </text>
    </svg>
  )
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await authApi.login(email, password)
      const { otp_token } = res.data
      navigate('/mission-control/otp', { state: { email, otp_token } })
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen" style={{ background: '#0A1628' }}>
      {/* Left side — AI illustration (hidden on small screens) */}
      <div className="hidden lg:flex items-center justify-center w-[60%] p-12">
        <div className="w-full max-w-lg">
          <AIIllustration />
        </div>
      </div>

      {/* Right side — Login card */}
      <div className="flex items-center justify-center w-full lg:w-[40%] px-6">
        <div
          className="w-full max-w-sm p-8 rounded-2xl"
          style={{ background: '#0F1F35', border: '1px solid #1E3A5F' }}
        >
          <div className="text-center mb-8">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold mx-auto mb-4 text-white"
              style={{ background: '#f97316' }}
            >
              MC
            </div>
            <h1
              className="text-2xl font-bold text-white"
              style={{ fontFamily: 'Space Grotesk, sans-serif' }}
            >
              Mission Control
            </h1>
            <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
              Admin access only
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="admin@mezzofy.com"
                className="w-full px-3 py-2.5 rounded-lg text-sm text-white border outline-none transition-colors focus:border-orange-500"
                style={{ background: '#1E2A3A', borderColor: '#374151' }}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2.5 rounded-lg text-sm text-white border outline-none transition-colors focus:border-orange-500"
                style={{ background: '#1E2A3A', borderColor: '#374151' }}
              />
            </div>

            {error && (
              <p className="text-xs text-red-400 bg-red-400/10 px-3 py-2 rounded-lg">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50"
              style={{ background: loading ? '#4B5563' : '#f97316' }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t text-center" style={{ borderColor: '#1E3A5F' }}>
            <p className="text-xs" style={{ color: '#374151' }}>
              v1.48.0 · Powered by <span style={{ color: '#f97316' }}>Mezzofy</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
