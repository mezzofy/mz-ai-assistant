import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import AppShell from './components/layout/AppShell'
import AdminRoute from './components/AdminRoute'
import LoginPage from './pages/LoginPage'
import OtpPage from './pages/OtpPage'
import DashboardPage from './pages/DashboardPage'
import SchedulerPage from './pages/SchedulerPage'
import AgentsPage from './pages/AgentsPage'
import FilesPage from './pages/FilesPage'
import TasksPage from './pages/TasksPage'
import UsersPage from './pages/UsersPage'
import CRMPage from './pages/CRMPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10000 },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/mission-control/login" element={<LoginPage />} />
          <Route path="/mission-control/otp" element={<OtpPage />} />

          <Route
            path="/mission-control"
            element={
              <AdminRoute>
                <AppShell />
              </AdminRoute>
            }
          >
            <Route index element={<Navigate to="/mission-control/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="scheduler" element={<SchedulerPage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="files" element={<FilesPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="crm" element={<CRMPage />} />
          </Route>

          <Route path="/" element={<Navigate to="/mission-control/login" replace />} />
          <Route path="*" element={<Navigate to="/mission-control/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
