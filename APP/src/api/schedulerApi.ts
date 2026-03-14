import {apiFetch} from './api';

export interface ScheduledJob {
  id: string;
  name: string;
  agent: string;
  message: string;
  schedule: string;          // cron string, e.g. "0 9 * * 1"
  deliver_to: {
    teams_channel?: string;
    email?: string[];
    push_user_id?: string;
  };
  is_active: boolean;
  next_run: string | null;   // ISO datetime
  last_run: string | null;
  created_at: string;
}

export interface ScheduledJobsResponse {
  jobs: ScheduledJob[];
  count: number;
}

export const listScheduledJobsApi = (): Promise<ScheduledJobsResponse> =>
  apiFetch<ScheduledJobsResponse>('/scheduler/jobs');
