import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '../api/auth'
import client from '../api/client'
import { useAuthStore } from '../stores/authStore'

export default function OtpPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const email = (location.state as { email?: string; otp_token?: string } | null)?.email || ''
  const otp_token = (location.state as { email?: string; otp_token?: string } | null)?.otp_token || ''
  const setAuth = useAuthStore((s) => s.setAuth)

  const [digits, setDigits] = useState(['', '', '', '', '', ''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [countdown, setCountdown] = useState(60)
  const inputs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (!email) navigate('/mission-control/login')
    inputs.current[0]?.focus()
  }, [email, navigate])

  useEffect(() => {
    if (countdown <= 0) return
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [countdown])

  const handleDigit = (idx: number, val: string) => {
    if (!/^\d*$/.test(val)) return
    const updated = [...digits]
    updated[idx] = val.slice(-1)
    setDigits(updated)
    if (val && idx < 5) inputs.current[idx + 1]?.focus()
    if (updated.every((d) => d)) handleVerify(updated.join(''))
  }

  const handleKey = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !digits[idx] && idx > 0) {
      inputs.current[idx - 1]?.focus()
    }
  }

  const handleVerify = async (code: string) => {
    setError('')
    setLoading(true)
    try {
      const res = await authApi.verifyOtp(otp_token, code)
      const { access_token, user_info } = res.data

      if (user_info?.role !== 'admin') {
        setError('Access denied: admin role required')
        setDigits(['', '', '', '', '', ''])
        setLoading(false)
        return
      }

      setAuth(access_token, {
        user_id: user_info.id,
        email: user_info.email,
        name: user_info.name,
        role: user_info.role,
      })
      navigate('/mission-control/dashboard')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Invalid OTP')
      setDigits(['', '', '', '', '', ''])
      inputs.current[0]?.focus()
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    if (countdown > 0) return
    try {
      await client.post('/auth/resend-otp', { otp_token })
      setCountdown(60)
    } catch {
      // ignore
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: '#0A0E1A' }}
    >
      <div
        className="w-full max-w-sm p-8 rounded-2xl border"
        style={{ background: '#111827', borderColor: '#1E2A3A' }}
      >
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Enter OTP
          </h1>
          <p className="text-sm mt-2" style={{ color: '#6B7280' }}>
            Sent to <span className="text-gray-300">{email}</span>
          </p>
        </div>

        <div className="flex justify-center gap-3 mb-6">
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => { inputs.current[i] = el }}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={(e) => handleDigit(i, e.target.value)}
              onKeyDown={(e) => handleKey(i, e)}
              disabled={loading}
              className="w-11 h-12 text-center text-lg font-mono font-bold text-white border rounded-lg outline-none transition-colors focus:border-indigo-500"
              style={{ background: '#1E2A3A', borderColor: d ? '#f97316' : '#374151' }}
            />
          ))}
        </div>

        {error && (
          <p className="text-xs text-red-400 text-center mb-4 bg-red-400/10 px-3 py-2 rounded-lg">
            {error}
          </p>
        )}

        {loading && (
          <p className="text-xs text-center text-gray-400 mb-4">Verifying...</p>
        )}

        <div className="text-center">
          <button
            onClick={handleResend}
            disabled={countdown > 0}
            className="text-sm transition-colors disabled:opacity-40"
            style={{ color: countdown > 0 ? '#6B7280' : '#f97316' }}
          >
            {countdown > 0 ? `Resend in ${countdown}s` : 'Resend OTP'}
          </button>
        </div>

        <div className="mt-4 flex justify-center">
          <button
            onClick={() => navigate('/mission-control/login')}
            className="px-6 py-2 rounded-lg text-sm border transition-colors hover:bg-white/5"
            style={{ color: '#6B7280', borderColor: '#374151' }}
          >
            ← Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
