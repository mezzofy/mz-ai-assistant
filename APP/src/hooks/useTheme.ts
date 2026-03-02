import {useSettingsStore} from '../stores/settingsStore';
import {BRAND, LIGHT_THEME, ThemeColors} from '../utils/theme';

export const useTheme = (): ThemeColors => {
  const appearance = useSettingsStore(s => s.appearance);
  return appearance === 'Light' ? LIGHT_THEME : BRAND;
};
