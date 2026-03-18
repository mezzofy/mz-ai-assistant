import React from 'react'
import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { LayoutDashboard, CalendarClock, Bot, FolderOpen, Users, LogOut } from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { path: '/mission-control/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/mission-control/scheduler', label: 'Scheduler', icon: CalendarClock },
  { path: '/mission-control/agents', label: 'Agents', icon: Bot },
  { path: '/mission-control/files', label: 'Files', icon: FolderOpen },
  { path: '/mission-control/users', label: 'Users', icon: Users },
]

export default function Sidebar() {
  const clearAuth = useAuthStore((s) => s.clearAuth)

  return (
    <aside
      className="w-56 flex flex-col border-r"
      style={{ background: '#111827', borderColor: '#1E3A5F' }}
    >
      {/* Logo */}
      <div className="px-5 py-5 border-b" style={{ borderColor: '#1E3A5F' }}>
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold"
            style={{ background: '#f97316' }}
          >
            MC
          </div>
          <div>
            <div className="text-sm font-semibold" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              Mission Control
            </div>
            <div className="text-xs" style={{ color: '#6B7280' }}>
              Mezzofy AI
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all',
                isActive
                  ? 'text-white font-medium'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              )
            }
            style={({ isActive }) =>
              isActive ? { background: 'rgba(249, 115, 22, 0.15)', color: '#f97316' } : {}
            }
          >
            <item.icon size={16} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Logout */}
      <div className="p-3 border-t" style={{ borderColor: '#1E3A5F' }}>
        <button
          onClick={() => clearAuth()}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-red-400/10 transition-all"
        >
          <LogOut size={16} /> Sign Out
        </button>
      </div>
    </aside>
  )
}
