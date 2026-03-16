import {create} from 'zustand';
import {getNotificationHistory, NotificationRecord} from '../api/notificationsApi';

type NotificationState = {
  notifications: NotificationRecord[];
  loading: boolean;
  error: string | null;
  loadNotifications: () => Promise<void>;
};

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  loading: false,
  error: null,

  loadNotifications: async () => {
    set({loading: true, error: null});
    try {
      const result = await getNotificationHistory(10);
      set({notifications: result.notifications, loading: false});
    } catch (e: any) {
      set({loading: false, error: e?.message ?? 'Failed to load notifications'});
    }
  },
}));
