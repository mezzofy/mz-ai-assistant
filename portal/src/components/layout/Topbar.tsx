import React from 'react'
import { useAuthStore } from '../../stores/authStore'

export default function Topbar() {
  const user = useAuthStore((s) => s.user)

  return (
    <header
      className="h-14 flex items-center justify-between px-6 border-b"
      style={{ background: '#111827', borderColor: '#1E2A3A' }}
    >
      <div className="text-sm text-gray-400">
        <span className="text-green-400">●</span> System Online
      </div>
      <div className="flex items-center gap-3">
        <div className="text-sm text-gray-300">{user?.email}</div>
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
          style={{ background: '#f97316' }}
        >
          {user?.name?.charAt(0)?.toUpperCase() || 'A'}
        </div>
      </div>
    </header>
  )
}
