import React, { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { LayoutDashboard, ListTodo, CalendarClock, Bot, FolderOpen, Users, TrendingUp, LogOut, Activity, Users2, CalendarRange } from 'lucide-react'
import clsx from 'clsx'
import { portalApi } from '../../api/portal'

const HR_ROLES = ['hr_viewer', 'hr_staff', 'hr_manager', 'executive', 'admin']

const NAV_ITEMS = [
  { path: '/mission-control/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/mission-control/background-tasks', label: 'Tasks', icon: Activity, badge: true },
  { path: '/mission-control/tasks', label: 'Messages', icon: ListTodo },
  { path: '/mission-control/scheduler', label: 'Scheduler', icon: CalendarClock },
  { path: '/mission-control/agents', label: 'Agents', icon: Bot },
  { path: '/mission-control/files', label: 'Files', icon: FolderOpen },
  { path: '/mission-control/crm', label: 'Leads', icon: TrendingUp },
]

const HR_NAV_ITEMS = [
  { path: '/mission-control/hr/employees', label: 'Employees', icon: Users2 },
  { path: '/mission-control/hr/leave', label: 'Leave', icon: CalendarRange },
]

const BOTTOM_NAV_ITEMS = [
  { path: '/mission-control/users', label: 'Users', icon: Users },
]

export default function Sidebar() {
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const user = useAuthStore((s) => s.user)
  const [activeBgCount, setActiveBgCount] = useState(0)
  const showHR = user?.role ? HR_ROLES.includes(user.role) : false

  useEffect(() => {
    let cancelled = false
    const fetchStats = async () => {
      try {
        const res = await portalApi.getTaskStats()
        if (!cancelled) {
          setActiveBgCount((res.data.running ?? 0) + (res.data.queued ?? 0))
        }
      } catch {
        // silently ignore — badge just won't show
      }
    }
    fetchStats()
    const interval = setInterval(fetchStats, 10000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

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
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
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
            <span className="flex-1">{item.label}</span>
            {item.badge && activeBgCount > 0 && (
              <span
                className="text-xs font-bold px-1.5 py-0.5 rounded-full"
                style={{ background: '#f97316', color: 'white', minWidth: '20px', textAlign: 'center' }}
              >
                {activeBgCount}
              </span>
            )}
          </NavLink>
        ))}

        {showHR && (
          <>
            <div className="pt-2 pb-1">
              <div className="px-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#4B5563' }}>
                HR
              </div>
            </div>
            {HR_NAV_ITEMS.map((item) => (
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
                <span className="flex-1">{item.label}</span>
              </NavLink>
            ))}
          </>
        )}

        <div className="pt-2 pb-1">
          <div className="border-t" style={{ borderColor: '#1E2A3A' }} />
        </div>

        {BOTTOM_NAV_ITEMS.map((item) => (
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
            <span className="flex-1">{item.label}</span>
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
