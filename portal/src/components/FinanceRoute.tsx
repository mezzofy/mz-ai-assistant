import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

const FINANCE_ROLES = ['finance_viewer', 'finance_manager', 'executive', 'admin', 'cfo', 'ceo']

export default function FinanceRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const user = useAuthStore((s) => s.user)

  if (!isAuthenticated) {
    return <Navigate to="/mission-control/login" replace />
  }

  if (!user?.role || !FINANCE_ROLES.includes(user.role)) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0A0E1A' }}>
        <div className="text-center">
          <div className="text-4xl mb-4">🚫</div>
          <h1 className="text-xl font-bold text-white mb-2">Access Denied</h1>
          <p className="text-gray-400">Finance role required to access this section</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
