import React from 'react';
import {View, Text, ScrollView, TouchableOpacity, StyleSheet} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useAuthStore} from '../stores/authStore';
import {useTheme} from '../hooks/useTheme';
import {DeptBadge} from '../components/shared/DeptBadge';

type InfoRowProps = {
  icon: string;
  label: string;
  value: string;
  colors: ReturnType<typeof useTheme>;
};

const InfoRow: React.FC<InfoRowProps> = ({icon, label, value, colors}) => (
  <View style={[styles.infoRow, {borderBottomColor: colors.border + '40'}]}>
    <View style={[styles.infoIcon, {backgroundColor: colors.accentSoft}]}>
      <Icon name={icon} size={16} color={colors.accent} />
    </View>
    <View style={styles.infoContent}>
      <Text style={[styles.infoLabel, {color: colors.textMuted}]}>{label}</Text>
      <Text style={[styles.infoValue, {color: colors.text}]}>{value}</Text>
    </View>
  </View>
);

export const ProfileScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const user = useAuthStore(s => s.user);
  const colors = useTheme();

  if (!user) {
    return null;
  }

  const initials = user.name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase();

  const roleDisplay = user.role
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());

  const deptDisplay = user.department
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, {color: colors.text}]}>Profile</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {/* Avatar Section */}
        <View style={styles.avatarSection}>
          <View style={[styles.avatarLarge, {backgroundColor: colors.accent}]}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
          <Text style={[styles.userName, {color: colors.text}]}>{user.name}</Text>
          <DeptBadge dept={user.department} />
        </View>

        {/* Info Card */}
        <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <InfoRow
            icon="mail-outline"
            label="Email"
            value={user.email}
            colors={colors}
          />
          <InfoRow
            icon="briefcase-outline"
            label="Role"
            value={roleDisplay}
            colors={colors}
          />
          <InfoRow
            icon="business-outline"
            label="Department"
            value={deptDisplay}
            colors={colors}
          />
        </View>

        {/* Permissions Card */}
        {user.permissions && user.permissions.length > 0 && (
          <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
            <Text style={[styles.sectionTitle, {color: colors.textMuted}]}>PERMISSIONS</Text>
            {user.permissions.map(perm => (
              <View key={perm} style={styles.permRow}>
                <Icon name="checkmark-circle" size={16} color={colors.accent} />
                <Text style={[styles.permText, {color: colors.text}]}>
                  {perm.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    paddingTop: 8,
    borderBottomWidth: 1,
  },
  backBtn: {padding: 4, marginRight: 8},
  headerTitle: {fontSize: 18, fontWeight: '700', flex: 1},
  headerSpacer: {width: 30},
  scroll: {flex: 1},
  scrollContent: {paddingBottom: 40},
  avatarSection: {alignItems: 'center', paddingVertical: 32, gap: 12},
  avatarLarge: {
    width: 88,
    height: 88,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {fontSize: 36, fontWeight: '800', color: '#fff'},
  userName: {fontSize: 22, fontWeight: '800'},
  card: {
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 14,
    borderWidth: 1,
    overflow: 'hidden',
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 14,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  infoIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoContent: {flex: 1},
  infoLabel: {fontSize: 11, fontWeight: '600', marginBottom: 2},
  infoValue: {fontSize: 14, fontWeight: '500'},
  sectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 8,
  },
  permRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  permText: {fontSize: 14},
});
