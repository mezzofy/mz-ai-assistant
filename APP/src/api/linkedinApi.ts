import {apiFetch} from './api';

export interface LinkedInStatusResponse {
  configured: boolean;
  session_preview: string | null;
  rate_limit: number;
  session_uses: number;
}

export const getLinkedInStatusApi = (): Promise<LinkedInStatusResponse> =>
  apiFetch<LinkedInStatusResponse>('/linkedin/status');
