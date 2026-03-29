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
  model_names?: {
    claude: string;
    kimi: string;
  };
}

export async function getSystemHealth(): Promise<SystemHealth | null> {
  try {
    return await apiFetch<SystemHealth>('/admin/health');
  } catch {
    // Non-admin: fall back to the public /health endpoint (DB + Redis only)
    try {
      const pub = await apiFetch<{
        status: string;
        services: {database: string; redis: string};
      }>('/health', {skipAuth: true});
      return {
        status: pub.status as 'ok' | 'degraded',
        services: {
          database: pub.services.database,
          redis: pub.services.redis,
          llm_manager: 'unknown',
        },
        connections: {websocket_active: 0},
      };
    } catch {
      return null;
    }
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
