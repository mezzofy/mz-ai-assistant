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

export interface ModelCheckResult {
  model: string;
  model_id: string;
  status: 'ok' | 'error';
  message: string;
  latency_ms: number;
}

export async function checkModelStatus(model: 'claude' | 'kimi'): Promise<ModelCheckResult | null> {
  try {
    return await apiFetch<ModelCheckResult>('/admin/model-check', {
      method: 'POST',
      body: JSON.stringify({model}),
    });
  } catch {
    return null;
  }
}
