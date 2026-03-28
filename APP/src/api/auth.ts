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

export interface OTPRequiredResponse {
  status: 'otp_required';
  otp_token: string;
  message: string;
}

export interface ResetOTPVerifiedResponse {
  status: string;
  reset_token: string;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

// Step 1 of login — returns otp_token, not JWT
export const loginApi = (email: string, password: string): Promise<OTPRequiredResponse> =>
  apiFetch<OTPRequiredResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({email, password}),
    skipAuth: true,
  });

// Step 2 of login — verify OTP → JWT tokens
export const verifyLoginOtpApi = (otp_token: string, code: string): Promise<LoginResponse> =>
  apiFetch<LoginResponse>('/auth/verify-otp', {
    method: 'POST',
    body: JSON.stringify({otp_token, code}),
    skipAuth: true,
  });

// Resend login OTP (60-second cooldown enforced by backend)
export const resendLoginOtpApi = (otp_token: string): Promise<{status: string}> =>
  apiFetch<{status: string}>('/auth/resend-otp', {
    method: 'POST',
    body: JSON.stringify({otp_token}),
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

// Forgot password — send reset OTP to email (always 200)
export const forgotPasswordApi = (email: string): Promise<{status: string; message: string}> =>
  apiFetch<{status: string; message: string}>('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({email}),
    skipAuth: true,
  });

// Verify reset OTP → short-lived reset_token
export const verifyResetOtpApi = (email: string, code: string): Promise<ResetOTPVerifiedResponse> =>
  apiFetch<ResetOTPVerifiedResponse>('/auth/verify-reset-otp', {
    method: 'POST',
    body: JSON.stringify({email, code}),
    skipAuth: true,
  });

// Complete password reset using reset_token
export const resetPasswordApi = (reset_token: string, new_password: string): Promise<{status: string}> =>
  apiFetch<{status: string}>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({reset_token, new_password}),
    skipAuth: true,
  });

// Activate a new account using invite token received by email
export const activateAccountApi = (
  invite_token: string,
  new_password: string,
): Promise<{activated: boolean; email: string; department: string}> =>
  apiFetch<{activated: boolean; email: string; department: string}>('/auth/activate', {
    method: 'POST',
    body: JSON.stringify({invite_token, new_password}),
    skipAuth: true,
  });

// Authenticated in-app password change
export const changePasswordApi = (
  current_password: string,
  new_password: string,
): Promise<{status: string}> =>
  apiFetch<{status: string}>('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({current_password, new_password}),
  });
