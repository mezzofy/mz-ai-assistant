import React from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import AppShell from './components/layout/AppShell'
import AdminRoute from './components/AdminRoute'
import HRRoute from './components/HRRoute'
import FinanceRoute from './components/FinanceRoute'
import SalesRoute from './components/SalesRoute'
import LoginPage from './pages/LoginPage'
import OtpPage from './pages/OtpPage'
import DashboardPage from './pages/DashboardPage'
import SchedulerPage from './pages/SchedulerPage'
import AgentsPage from './pages/AgentsPage'
import FilesPage from './pages/FilesPage'
import TasksPage from './pages/TasksPage'
import UsersPage from './pages/UsersPage'
import CRMPage from './pages/CRMPage'
import CRMLeadDetailPage from './pages/CRMLeadDetailPage'
import BackgroundTasksPage from './pages/BackgroundTasksPage'
import HREmployeesPage from './pages/hr/HREmployeesPage'
import HREmployeeProfilePage from './pages/hr/HREmployeeProfilePage'
import HREmployeeFormPage from './pages/hr/HREmployeeFormPage'
import HRLeaveManagementPage from './pages/hr/HRLeaveManagementPage'
import FinanceDashboard from './pages/finance/FinanceDashboard'
import Invoices from './pages/finance/Invoices'
import JournalEntries from './pages/finance/JournalEntries'
import Bills from './pages/finance/Bills'
import Payments from './pages/finance/Payments'
import Customers from './pages/finance/Customers'
import Vendors from './pages/finance/Vendors'
import Expenses from './pages/finance/Expenses'
import Reports from './pages/finance/Reports'
import BankAccounts from './pages/finance/BankAccounts'
import Shareholders from './pages/finance/Shareholders'
import Entities from './pages/finance/Entities'
import Periods from './pages/finance/Periods'
import TaxCodes from './pages/finance/TaxCodes'
import Quotes from './pages/finance/Quotes'
import DeptFilesPage from './pages/DeptFilesPage'

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
            <Route path="crm" element={<SalesRoute><CRMPage /></SalesRoute>} />
            <Route path="crm/leads/:id" element={<SalesRoute><CRMLeadDetailPage /></SalesRoute>} />
            <Route path="background-tasks" element={<BackgroundTasksPage />} />
            <Route path="finance" element={<FinanceRoute><FinanceDashboard /></FinanceRoute>} />
            <Route path="finance/journal" element={<FinanceRoute><JournalEntries /></FinanceRoute>} />
            <Route path="finance/invoices" element={<FinanceRoute><Invoices /></FinanceRoute>} />
            <Route path="finance/bills" element={<FinanceRoute><Bills /></FinanceRoute>} />
            <Route path="finance/payments" element={<FinanceRoute><Payments /></FinanceRoute>} />
            <Route path="finance/customers" element={<FinanceRoute><Customers /></FinanceRoute>} />
            <Route path="finance/vendors" element={<FinanceRoute><Vendors /></FinanceRoute>} />
            <Route path="finance/expenses" element={<FinanceRoute><Expenses /></FinanceRoute>} />
            <Route path="finance/reports" element={<FinanceRoute><Reports /></FinanceRoute>} />
            <Route path="finance/bank-accounts" element={<FinanceRoute><BankAccounts /></FinanceRoute>} />
            <Route path="finance/shareholders" element={<FinanceRoute><Shareholders /></FinanceRoute>} />
            <Route path="finance/entities" element={<FinanceRoute><Entities /></FinanceRoute>} />
            <Route path="finance/periods" element={<FinanceRoute><Periods /></FinanceRoute>} />
            <Route path="finance/tax" element={<FinanceRoute><TaxCodes /></FinanceRoute>} />
            <Route path="finance/quotes" element={<FinanceRoute><Quotes /></FinanceRoute>} />
            <Route path="finance/files" element={<FinanceRoute><DeptFilesPage department="finance" sectionTitle="Finance" /></FinanceRoute>} />
            <Route path="sales/files" element={<SalesRoute><DeptFilesPage department="sales" sectionTitle="Sales" /></SalesRoute>} />
            <Route path="hr" element={<HRRoute><Outlet /></HRRoute>}>
              <Route path="employees" element={<HREmployeesPage />} />
              <Route path="employees/new" element={<HREmployeeFormPage />} />
              <Route path="employees/:id" element={<HREmployeeProfilePage />} />
              <Route path="employees/:id/edit" element={<HREmployeeFormPage />} />
              <Route path="leave" element={<HRLeaveManagementPage />} />
              <Route path="files" element={<DeptFilesPage department="hr" sectionTitle="HR" />} />
            </Route>
          </Route>

          <Route path="/" element={<Navigate to="/mission-control/login" replace />} />
          <Route path="*" element={<Navigate to="/mission-control/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
