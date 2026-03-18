import client from './client'

export const authApi = {
  login: (email: string, password: string) =>
    client.post('/auth/login', { email, password }),

  verifyOtp: (otp_token: string, code: string) =>
    client.post('/auth/verify-otp', { otp_token, code }),

  getMe: () =>
    client.get('/api/admin-portal/auth/me'),

  logout: () =>
    client.post('/auth/logout').catch(() => {}),
}
