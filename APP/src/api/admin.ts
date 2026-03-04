import {apiFetch} from './api';

export interface SystemHealth {
  status: 'ok' | 'degraded';
  services: {
    database: string;
    redis: string;
    llm_manager: string;
  };
  connections: {
    websocket_active: number;
  };
}

export async function getSystemHealth(): Promise<SystemHealth | null> {
  try {
    return await apiFetch<SystemHealth>('/admin/health');
  } catch {
    // Non-admin users receive 403 — return null for graceful degradation
    return null;
  }
}
