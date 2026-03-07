import {create} from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {getStorageStatsApi} from '../api/files';

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) { return `${bytes} B`; }
  if (bytes < 1024 * 1024) { return `${(bytes / 1024).toFixed(1)} KB`; }
  if (bytes < 1024 * 1024 * 1024) { return `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
};

type SettingsState = {
  notifications: boolean;
  speechLanguage: string;
  appearance: 'Dark' | 'Light';
  storageDisplay: string | null;
  toggleNotifications: () => void;
  setSpeechLanguage: (lang: string) => void;
  setAppearance: (v: 'Dark' | 'Light') => void;
  loadSettings: () => Promise<void>;
  loadStorageInfo: () => Promise<void>;
};

export const useSettingsStore = create<SettingsState>((set, get) => ({
  notifications: true,
  speechLanguage: 'English',
  appearance: 'Dark',
  storageDisplay: null,

  toggleNotifications: () => {
    const next = !get().notifications;
    set({notifications: next});
    AsyncStorage.setItem('@mz_settings_notifications', JSON.stringify(next)).catch(() => {});
  },

  setSpeechLanguage: (lang) => {
    set({speechLanguage: lang});
    AsyncStorage.setItem('@mz_settings_speechLanguage', lang).catch(() => {});
  },

  setAppearance: (v) => {
    set({appearance: v});
    AsyncStorage.setItem('@mz_settings_appearance', v).catch(() => {});
  },

  loadSettings: async () => {
    const [notif, lang, appearance] = await Promise.all([
      AsyncStorage.getItem('@mz_settings_notifications'),
      AsyncStorage.getItem('@mz_settings_speechLanguage'),
      AsyncStorage.getItem('@mz_settings_appearance'),
    ]);
    set({
      notifications: notif !== null ? JSON.parse(notif) : true,
      speechLanguage: lang ?? 'English',
      appearance: (appearance as 'Dark' | 'Light' | null) ?? 'Dark',
    });
  },

  loadStorageInfo: async () => {
    try {
      const result = await getStorageStatsApi();
      set({storageDisplay: formatBytes(result.total_bytes)});
    } catch {
      // Silent — keep null
    }
  },
}));
