import client from './client'

export const authApi = {
  login: (email: string, password: string) =>
    client.post('/auth/login', { email, password }),

  verifyOtp: (email: string, otp: string) =>
    client.post('/auth/verify-otp', { email, otp }),

  getMe: () =>
    client.get('/api/admin-portal/auth/me'),

  logout: () =>
    client.post('/auth/logout').catch(() => {}),
}
