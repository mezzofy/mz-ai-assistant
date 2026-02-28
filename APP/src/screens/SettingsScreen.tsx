import React from 'react';
import {View, Text, ScrollView, TouchableOpacity, StyleSheet} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {BRAND} from '../utils/theme';
import {useAuthStore} from '../stores/authStore';
import {DeptBadge} from '../components/shared/DeptBadge';

type RowProps = {
  icon: string;
  label: string;
  value?: string;
  accent?: boolean;
  danger?: boolean;
  onPress?: () => void;
};

const SettingsRow: React.FC<RowProps> = ({icon, label, value, accent, danger, onPress}) => (
  <TouchableOpacity onPress={onPress} style={styles.row} activeOpacity={0.7}>
    <View style={[styles.rowIcon, danger && styles.rowIconDanger, accent && styles.rowIconAccent]}>
      <Icon name={icon} size={18} color={danger ? BRAND.danger : accent ? BRAND.accent : BRAND.textMuted} />
    </View>
    <Text style={[styles.rowLabel, danger && {color: BRAND.danger}]}>{label}</Text>
    {value && <Text style={styles.rowValue}>{value}</Text>}
    <Icon name="chevron-forward" size={16} color={BRAND.textDim} />
  </TouchableOpacity>
);

export const SettingsScreen: React.FC = () => {
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);

  if (!user) {
    return null;
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Settings</Text>
      </View>
      <ScrollView style={styles.list}>
        {/* Profile Card */}
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {user.name.split(' ').map(n => n[0]).join('')}
            </Text>
          </View>
          <View>
            <Text style={styles.profileName}>{user.name}</Text>
            <Text style={styles.profileEmail}>{user.email}</Text>
            <DeptBadge dept={user.department} />
          </View>
        </View>

        <View style={styles.group}>
          <SettingsRow icon="person-outline" label="Edit Profile" />
          <SettingsRow icon="notifications-outline" label="Notifications" value="On" />
          <SettingsRow icon="mic-outline" label="Speech Language" value="English" />
          <SettingsRow icon="eye-outline" label="Appearance" value="Dark" />
        </View>

        <View style={styles.group}>
          <SettingsRow icon="shield-outline" label="Privacy & Security" accent />
          <SettingsRow icon="document-outline" label="Storage & Data" value="142 MB" />
          <SettingsRow icon="time-outline" label="AI Usage Stats" accent />
        </View>

        <View style={styles.group}>
          <SettingsRow icon="log-out-outline" label="Sign Out" danger onPress={() => { logout(); }} />
        </View>

        <Text style={styles.version}>Mezzofy AI Assistant v1.0.0</Text>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: BRAND.primary},
  header: {padding: 16, paddingBottom: 8},
  title: {color: BRAND.text, fontSize: 20, fontWeight: '800'},
  list: {flex: 1, paddingHorizontal: 16},
  profileCard: {flexDirection: 'row', alignItems: 'center', gap: 14, padding: 20, borderRadius: 16, marginBottom: 16, backgroundColor: BRAND.surfaceLight, borderWidth: 1, borderColor: BRAND.border},
  avatar: {width: 56, height: 56, borderRadius: 16, backgroundColor: BRAND.accent, alignItems: 'center', justifyContent: 'center'},
  avatarText: {fontSize: 22, fontWeight: '800', color: '#fff'},
  profileName: {color: BRAND.text, fontSize: 17, fontWeight: '700'},
  profileEmail: {color: BRAND.textMuted, fontSize: 13, marginVertical: 2},
  group: {borderRadius: 14, overflow: 'hidden', marginBottom: 12, backgroundColor: BRAND.surfaceLight, borderWidth: 1, borderColor: BRAND.border},
  row: {flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, paddingHorizontal: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: BRAND.border + '40'},
  rowIcon: {width: 36, height: 36, borderRadius: 10, backgroundColor: BRAND.surface, alignItems: 'center', justifyContent: 'center'},
  rowIconDanger: {backgroundColor: '#FF4B6E14'},
  rowIconAccent: {backgroundColor: BRAND.accentSoft},
  rowLabel: {flex: 1, fontSize: 14, color: BRAND.text, fontWeight: '500'},
  rowValue: {fontSize: 13, color: BRAND.textMuted, marginRight: 4},
  version: {textAlign: 'center', color: BRAND.textDim, fontSize: 11, marginVertical: 20},
});
