import {apiFetch} from './api';

export interface MsAuthUrlResponse {
  auth_url: string;
  state: string;
}

export interface MsAuthCallbackResponse {
  connected: boolean;
  ms_email: string;
  scopes: string[];
}

export interface MsAuthStatusResponse {
  connected: boolean;
  ms_email: string | null;
  scopes: string[];
  expires_at: string | null;
}

export interface MsDisconnectResponse {
  disconnected: boolean;
}

export const getMsAuthUrlApi = (): Promise<MsAuthUrlResponse> =>
  apiFetch<MsAuthUrlResponse>('/ms/auth/url');

export const postMsAuthCallbackApi = (
  code: string,
  state: string,
): Promise<MsAuthCallbackResponse> =>
  apiFetch<MsAuthCallbackResponse>('/ms/auth/callback', {
    method: 'POST',
    body: JSON.stringify({code, state}),
  });

export const getMsAuthStatusApi = (): Promise<MsAuthStatusResponse> =>
  apiFetch<MsAuthStatusResponse>('/ms/auth/status');

export const deleteMsAuthDisconnectApi = (): Promise<MsDisconnectResponse> =>
  apiFetch<MsDisconnectResponse>('/ms/auth/disconnect', {method: 'DELETE'});
