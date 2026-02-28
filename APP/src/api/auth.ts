import {apiFetch} from './api';

export interface UserInfo {
  id: string;
  email: string;
  name: string;
  role: string;
  department: string;
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_info: UserInfo; // Full user data already included — no extra /auth/me call needed
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

// skipAuth: no token exists yet
export const loginApi = (email: string, password: string): Promise<LoginResponse> =>
  apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({email, password}),
    skipAuth: true,
  });

// skipAuth: access token may be expired; refresh token is in the body
export const refreshTokenApi = (refreshToken: string): Promise<RefreshResponse> =>
  apiFetch<RefreshResponse>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({refresh_token: refreshToken}),
    skipAuth: true,
  });

// NO skipAuth — server requires Depends(get_current_user) on /auth/logout
export const logoutApi = (refreshToken: string): Promise<void> =>
  apiFetch<void>('/auth/logout', {
    method: 'POST',
    body: JSON.stringify({refresh_token: refreshToken}),
  });

// Default auth — requires valid access token
export const getMeApi = (): Promise<UserInfo> => apiFetch<UserInfo>('/auth/me');
