import {apiFetch} from './api';

const HR = '/api/admin-portal/hr';

// ── Types ─────────────────────────────────────────────────────────────────────

interface HRResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
}

export interface LeaveBalance {
  leave_type_id?: string;
  leave_type_name?: string;
  entitled: number;
  used: number;
  remaining: number;
}

export interface MyLeaveBalanceData {
  employee_id: string;
  employee_name?: string;
  year: number;
  balances: LeaveBalance[];
}

export interface LeaveApplication {
  id: string;
  employee_id: string;
  leave_type_id: string;
  leave_type_name?: string;
  start_date: string;
  end_date: string;
  total_days: number;
  half_day?: boolean;
  reason?: string;
  status: string;
  comment?: string;
  created_at: string;
}

export interface LeaveType {
  id: string;
  name: string;
  country?: string;
}

// ── API calls ──────────────────────────────────────────────────────────────────

export const getMyLeaveBalance = () =>
  apiFetch<HRResponse<MyLeaveBalanceData>>(`${HR}/leave/balance`);

export const getMyLeaveApplications = () =>
  apiFetch<HRResponse<{applications: LeaveApplication[]; count: number}>>(
    `${HR}/leave/applications`,
  );

export const getLeaveTypes = (country?: string) =>
  apiFetch<HRResponse<{leave_types: LeaveType[]}>>(
    `${HR}/leave/types${country ? `?country=${encodeURIComponent(country)}` : ''}`,
  );

export const applyLeave = (data: {
  leave_type_id: string;
  start_date: string;
  end_date: string;
  total_days: number;
  half_day?: boolean;
  reason?: string;
}) =>
  apiFetch<HRResponse<{application: LeaveApplication}>>(`${HR}/leave/apply`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const cancelLeave = (applicationId: string) =>
  apiFetch<HRResponse<unknown>>(
    `${HR}/leave/applications/${applicationId}/status`,
    {
      method: 'PATCH',
      body: JSON.stringify({status: 'cancelled', comment: 'Cancelled by employee'}),
    },
  );
