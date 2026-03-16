import {apiFetch} from './api';

export type NotificationRecord = {
  id: string;
  title: string;
  body: string;
  data: Record<string, unknown> | null;
  sent_at: string;
};

export type NotificationHistoryResponse = {
  notifications: NotificationRecord[];
  count: number;
};

export const registerDevice = (device_token: string, platform: 'android' | 'ios' = 'android') =>
  apiFetch<{registered: boolean}>('/notifications/register-device', {
    method: 'POST',
    body: JSON.stringify({device_token, platform}),
  });

export const unregisterDevice = (device_token: string, platform: 'android' | 'ios' = 'android') =>
  apiFetch<{unregistered: boolean}>('/notifications/unregister-device', {
    method: 'DELETE',
    body: JSON.stringify({device_token, platform}),
  });

export const updatePushPreference = (push_notifications_enabled: boolean) =>
  apiFetch<{push_notifications_enabled: boolean}>('/notifications/preferences', {
    method: 'PUT',
    body: JSON.stringify({push_notifications_enabled}),
  });

export const getNotificationHistory = (limit = 10): Promise<NotificationHistoryResponse> =>
  apiFetch<NotificationHistoryResponse>(`/notifications/history?limit=${limit}`);
