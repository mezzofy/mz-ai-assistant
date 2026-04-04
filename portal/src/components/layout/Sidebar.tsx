import React, { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { LayoutDashboard, ListTodo, CalendarClock, Bot, FolderOpen, Users, TrendingUp, LogOut, Activity, Users2, CalendarRange, BarChart3, BookOpen, FileText, MessageSquare, Inbox, CreditCard, UserCircle, Building, Building2, Landmark, Receipt, PieChart, LayoutList, Tag, ChevronDown, Settings } from 'lucide-react'
import clsx from 'clsx'
import { portalApi } from '../../api/portal'

const HR_ROLES = ['hr_viewer', 'hr_staff', 'hr_manager', 'executive', 'admin']
const FINANCE_ROLES = ['finance_viewer', 'finance_manager', 'executive', 'admin', 'cfo', 'ceo']
const SALES_ROLES = ['sales_manager', 'sales_rep', 'executive', 'admin']

type FinanceLeafItem = { path: string; label: string; icon: React.ComponentType<{ size?: number }> }
type FinanceNavItem =
  | { type: 'link'; path: string; label: string; icon: React.ComponentType<{ size?: number }> }
  | { type: 'group'; label: string; icon: React.ComponentType<{ size?: number }>; children: FinanceLeafItem[] }

const FINANCE_NAV_ITEMS: FinanceNavItem[] = [
  { type: 'link', path: '/mission-control/finance', label: 'Dashboard', icon: BarChart3 },
  { type: 'link', path: '/mission-control/finance/journal', label: 'Journal Entries', icon: BookOpen },
  {
    type: 'group', label: 'Receivables', icon: FileText,
    children: [
      { path: '/mission-control/finance/invoices', label: 'Invoices', icon: FileText },
    ]
  },
  {
    type: 'group', label: 'Payables', icon: Inbox,
    children: [
      { path: '/mission-control/finance/bills', label: 'Bills', icon: Inbox },
      { path: '/mission-control/finance/expenses', label: 'Expenses', icon: Receipt },
      { path: '/mission-control/finance/payments', label: 'Payments', icon: CreditCard },
    ]
  },
  { type: 'link', path: '/mission-control/finance/reports', label: 'Reports', icon: PieChart },
  {
    type: 'group', label: 'Settings', icon: Settings,
    children: [
      { path: '/mission-control/finance/entities', label: 'Legal Entities', icon: Building },
      { path: '/mission-control/finance/accounts', label: 'Chart of Accounts', icon: LayoutList },
      { path: '/mission-control/finance/bank-accounts', label: 'Bank Accounts', icon: Landmark },
      { path: '/mission-control/finance/vendors', label: 'Vendors', icon: Building2 },
      { path: '/mission-control/finance/tax-codes', label: 'Tax Codes', icon: Tag },
    ]
  },
  { type: 'link', path: '/mission-control/finance/files', label: 'Files', icon: FolderOpen },
]

const NAV_ITEMS = [
  { path: '/mission-control/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/mission-control/background-tasks', label: 'Tasks', icon: Activity, badge: true },
  { path: '/mission-control/tasks', label: 'Messages', icon: ListTodo },
  { path: '/mission-control/scheduler', label: 'Scheduler', icon: CalendarClock },
  { path: '/mission-control/agents', label: 'Agents', icon: Bot },
  { path: '/mission-control/files', label: 'Files', icon: FolderOpen },
]

const SALES_NAV_ITEMS = [
  { path: '/mission-control/crm', label: 'Leads', icon: TrendingUp },
  { path: '/mission-control/sales/customers', label: 'Customers', icon: UserCircle },
  { path: '/mission-control/sales/quotes', label: 'Quotes', icon: MessageSquare },
  { path: '/mission-control/sales/files', label: 'Files', icon: FolderOpen },
]

const HR_NAV_ITEMS = [
  { path: '/mission-control/hr/employees', label: 'Employees', icon: Users2 },
  { path: '/mission-control/hr/leave', label: 'Leave', icon: CalendarRange },
  { path: '/mission-control/hr/files', label: 'Files', icon: FolderOpen },
]

const BOTTOM_NAV_ITEMS = [
  { path: '/mission-control/users', label: 'Users', icon: Users },
]

export default function Sidebar() {
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const user = useAuthStore((s) => s.user)
  const location = useLocation()
  const [activeBgCount, setActiveBgCount] = useState(0)

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    FINANCE_NAV_ITEMS.forEach(item => {
      if (item.type === 'group') {
        initial[item.label] = item.children.some(c => location.pathname.startsWith(c.path))
      }
    })
    return initial
  })

  const toggleGroup = (label: string) =>
    setOpenGroups(prev => ({ ...prev, [label]: !prev[label] }))
  const showHR = user?.role ? HR_ROLES.includes(user.role) : false
  const showFinance = user?.role ? FINANCE_ROLES.includes(user.role) : false
  const showSales = user?.role ? SALES_ROLES.includes(user.role) : false
  const showUsers = user?.role === 'admin'
  const CORE_ROLES = ['admin', 'executive']
  const showCore = user?.role ? CORE_ROLES.includes(user.role) : false

  useEffect(() => {
    if (!showCore) return
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
  }, [showCore])

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
        {showCore && NAV_ITEMS.map((item) => (
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

        {showSales && (
          <>
            <div className="pt-2 pb-1">
              <div className="px-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#4B5563' }}>
                Sales
              </div>
            </div>
            {SALES_NAV_ITEMS.map((item) => (
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

        {showFinance && (
          <>
            <div className="pt-2 pb-1">
              <div className="px-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#4B5563' }}>
                Finance
              </div>
            </div>
            {FINANCE_NAV_ITEMS.map((item) => {
              if (item.type === 'link') {
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/mission-control/finance'}
                    className={({ isActive }) =>
                      clsx('flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all',
                        isActive ? 'text-white font-medium' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5')
                    }
                    style={({ isActive }) => isActive ? { background: 'rgba(249, 115, 22, 0.15)', color: '#f97316' } : {}}
                  >
                    <item.icon size={16} />
                    <span className="flex-1">{item.label}</span>
                  </NavLink>
                )
              }

              if (item.type === 'group') {
                const isOpen = openGroups[item.label] ?? false
                return (
                  <div key={`group-${item.label}`}>
                    <button
                      onClick={() => toggleGroup(item.label)}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all text-gray-400 hover:text-gray-200 hover:bg-white/5"
                    >
                      <item.icon size={16} />
                      <span className="flex-1 text-left">{item.label}</span>
                      <ChevronDown
                        size={14}
                        className="transition-transform duration-200"
                        style={{ transform: isOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}
                      />
                    </button>

                    {isOpen && (
                      <div className="ml-3 pl-3 border-l" style={{ borderColor: '#1E2A3A' }}>
                        {item.children.map(child => (
                          <NavLink
                            key={child.path}
                            to={child.path}
                            className={({ isActive }) =>
                              clsx('flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-all',
                                isActive ? 'text-white font-medium' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5')
                            }
                            style={({ isActive }) => isActive ? { background: 'rgba(249, 115, 22, 0.15)', color: '#f97316' } : {}}
                          >
                            <child.icon size={14} />
                            <span className="flex-1">{child.label}</span>
                          </NavLink>
                        ))}
                      </div>
                    )}
                  </div>
                )
              }

              return null
            })}
          </>
        )}

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

        {showUsers && BOTTOM_NAV_ITEMS.map((item) => (
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
