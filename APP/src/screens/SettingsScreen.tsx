import React, {useEffect} from 'react';
import {View, Text, ScrollView, TouchableOpacity, StyleSheet} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {useAuthStore} from '../stores/authStore';
import {useSettingsStore} from '../stores/settingsStore';
import {useMsStore} from '../stores/msStore';
import {DeptBadge} from '../components/shared/DeptBadge';

type RowProps = {
  icon: string;
  label: string;
  value?: string;
  accent?: boolean;
  danger?: boolean;
  onPress?: () => void;
};

const SettingsRow: React.FC<RowProps & {colors: ReturnType<typeof useTheme>}> = (
  {icon, label, value, accent, danger, onPress, colors},
) => (
  <TouchableOpacity onPress={onPress} style={styles.row} activeOpacity={0.7}>
    <View style={[
      styles.rowIcon,
      danger && {backgroundColor: '#FF4B6E14'},
      accent && {backgroundColor: colors.accentSoft},
      !danger && !accent && {backgroundColor: colors.surface},
    ]}>
      <Icon name={icon} size={18} color={danger ? colors.danger : accent ? colors.accent : colors.textMuted} />
    </View>
    <Text style={[styles.rowLabel, {color: danger ? colors.danger : colors.text}]}>{label}</Text>
    {value && <Text style={[styles.rowValue, {color: colors.textMuted}]}>{value}</Text>}
    <Icon name="chevron-forward" size={16} color={colors.textDim} />
  </TouchableOpacity>
);

export const SettingsScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);
  const {
    notifications, speechLanguage, appearance, storageDisplay,
    toggleNotifications, setSpeechLanguage, setAppearance, loadSettings, loadStorageInfo,
  } = useSettingsStore();
  const {connected: msConnected, msEmail, loadStatus: loadMsStatus} = useMsStore();
  const colors = useTheme();

  useEffect(() => {
    loadSettings();
    loadStorageInfo();
    loadMsStatus();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!user) {
    return null;
  }

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      <View style={styles.header}>
        <Text style={[styles.title, {color: colors.text}]}>Settings</Text>
      </View>
      <ScrollView style={styles.list}>
        {/* Profile Card */}
        <View style={[styles.profileCard, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <View style={[styles.avatar, {backgroundColor: colors.accent}]}>
            <Text style={styles.avatarText}>
              {user.name.split(' ').map(n => n[0]).join('')}
            </Text>
          </View>
          <View>
            <Text style={[styles.profileName, {color: colors.text}]}>{user.name}</Text>
            <Text style={[styles.profileEmail, {color: colors.textMuted}]}>{user.email}</Text>
            <DeptBadge dept={user.department} />
          </View>
        </View>

        <View style={[styles.group, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          {/* Edit Profile → navigates to ProfileScreen */}
          <SettingsRow
            icon="person-outline"
            label="Edit Profile"
            colors={colors}
            onPress={() => navigation.navigate('Profile')}
          />

          {/* Notifications — On / Off segmented control */}
          <View style={[styles.row, {borderBottomColor: colors.border + '40'}]}>
            <View style={[styles.rowIcon, {backgroundColor: colors.surface}]}>
              <Icon name="notifications-outline" size={18} color={colors.textMuted} />
            </View>
            <Text style={[styles.rowLabel, {color: colors.text}]}>Notifications</Text>
            <View style={[styles.segmentWrap, {borderColor: colors.border}]}>
              {(['On', 'Off'] as const).map(opt => {
                const isActive = opt === 'On' ? notifications : !notifications;
                return (
                  <TouchableOpacity
                    key={opt}
                    onPress={() => {
                      if ((opt === 'On' && !notifications) || (opt === 'Off' && notifications)) {
                        toggleNotifications();
                      }
                    }}
                    style={[
                      styles.segmentBtn,
                      {backgroundColor: isActive ? colors.accent : colors.surface},
                    ]}>
                    <Text style={[styles.segmentText, {color: isActive ? '#fff' : colors.textMuted}]}>
                      {opt}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Speech Language — English / Chinese segmented control */}
          <View style={[styles.row, {borderBottomColor: colors.border + '40'}]}>
            <View style={[styles.rowIcon, {backgroundColor: colors.surface}]}>
              <Icon name="mic-outline" size={18} color={colors.textMuted} />
            </View>
            <Text style={[styles.rowLabel, {color: colors.text}]}>Speech Language</Text>
            <View style={[styles.segmentWrap, {borderColor: colors.border}]}>
              {(['English', 'Chinese'] as const).map(opt => {
                const isActive = speechLanguage === opt;
                return (
                  <TouchableOpacity
                    key={opt}
                    onPress={() => setSpeechLanguage(opt)}
                    style={[
                      styles.segmentBtn,
                      {backgroundColor: isActive ? colors.accent : colors.surface},
                    ]}>
                    <Text style={[styles.segmentText, {color: isActive ? '#fff' : colors.textMuted}]}>
                      {opt}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Appearance — Dark / Light segmented control */}
          <View style={[styles.row, {borderBottomColor: 'transparent'}]}>
            <View style={[styles.rowIcon, {backgroundColor: colors.surface}]}>
              <Icon name="eye-outline" size={18} color={colors.textMuted} />
            </View>
            <Text style={[styles.rowLabel, {color: colors.text}]}>Appearance</Text>
            <View style={[styles.segmentWrap, {borderColor: colors.border}]}>
              {(['Dark', 'Light'] as const).map(opt => {
                const isActive = appearance === opt;
                return (
                  <TouchableOpacity
                    key={opt}
                    onPress={() => setAppearance(opt)}
                    style={[
                      styles.segmentBtn,
                      {backgroundColor: isActive ? colors.accent : colors.surface},
                    ]}>
                    <Text style={[styles.segmentText, {color: isActive ? '#fff' : colors.textMuted}]}>
                      {opt}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        </View>

        <View style={[styles.group, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <SettingsRow icon="shield-outline" label="Privacy & Security" accent colors={colors} onPress={() => navigation.navigate('PrivacySecurity')} />
          <SettingsRow
            icon="document-outline"
            label="Storage & Data"
            value={storageDisplay !== null ? storageDisplay : '—'}
            colors={colors}
          />
          <SettingsRow icon="time-outline" label="AI Usage Stats" accent colors={colors} onPress={() => navigation.navigate('AIUsageStats')} />
          <SettingsRow
            icon="logo-windows"
            label="Connected Accounts"
            value={msConnected && msEmail ? msEmail : undefined}
            accent
            colors={colors}
            onPress={() => navigation.navigate('ConnectedAccounts')}
          />
        </View>

        <View style={[styles.group, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <SettingsRow icon="log-out-outline" label="Sign Out" danger colors={colors} onPress={() => { logout(); }} />
        </View>

        <Text style={[styles.version, {color: colors.textDim}]}>Mezzofy AI Assistant v1.22.0</Text>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {padding: 16, paddingBottom: 8},
  title: {fontSize: 20, fontWeight: '800'},
  list: {flex: 1, paddingHorizontal: 16},
  profileCard: {flexDirection: 'row', alignItems: 'center', gap: 14, padding: 20, borderRadius: 16, marginBottom: 16, borderWidth: 1},
  avatar: {width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center'},
  avatarText: {fontSize: 22, fontWeight: '800', color: '#fff'},
  profileName: {fontSize: 17, fontWeight: '700'},
  profileEmail: {fontSize: 13, marginVertical: 2},
  group: {borderRadius: 14, overflow: 'hidden', marginBottom: 12, borderWidth: 1},
  row: {flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, paddingHorizontal: 16, borderBottomWidth: StyleSheet.hairlineWidth},
  rowIcon: {width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center'},
  rowLabel: {flex: 1, fontSize: 14, fontWeight: '500'},
  rowValue: {fontSize: 13, marginRight: 4},
  segmentWrap: {flexDirection: 'row', borderRadius: 8, borderWidth: 1, overflow: 'hidden'},
  segmentBtn: {paddingHorizontal: 14, paddingVertical: 6},
  segmentText: {fontSize: 12, fontWeight: '600'},
  version: {textAlign: 'center', fontSize: 11, marginVertical: 20},
});
