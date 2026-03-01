import {create} from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {listFilesApi} from '../api/files';

type SettingsState = {
  notifications: boolean;
  speechLanguage: string;
  appearance: 'Dark' | 'Light';
  fileCount: number | null;
  toggleNotifications: () => void;
  setSpeechLanguage: (lang: string) => void;
  setAppearance: (v: 'Dark' | 'Light') => void;
  loadSettings: () => Promise<void>;
  loadFileCount: () => Promise<void>;
};

export const useSettingsStore = create<SettingsState>((set, get) => ({
  notifications: true,
  speechLanguage: 'English',
  appearance: 'Dark',
  fileCount: null,

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

  loadFileCount: async () => {
    try {
      const result = await listFilesApi();
      set({fileCount: result.count});
    } catch {
      // Silent — keep null
    }
  },
}));
