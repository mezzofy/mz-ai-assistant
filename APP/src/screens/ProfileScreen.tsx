import React, {useEffect, useState} from 'react';
import {View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useAuthStore} from '../stores/authStore';
import {useTheme} from '../hooks/useTheme';
import {DeptBadge} from '../components/shared/DeptBadge';
import {
  getMyLeaveBalance, getMyLeaveApplications, cancelLeave,
  type MyLeaveBalanceData, type LeaveApplication,
} from '../api/hrApi';

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

  const [leaveBalance, setLeaveBalance] = useState<MyLeaveBalanceData | null>(null);
  const [leaveApps, setLeaveApps] = useState<LeaveApplication[]>([]);
  const [hrLoading, setHrLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [balRes, appsRes] = await Promise.all([
          getMyLeaveBalance(),
          getMyLeaveApplications(),
        ]);
        if (!cancelled) {
          if (balRes?.data) { setLeaveBalance(balRes.data); }
          if (appsRes?.data?.applications) { setLeaveApps(appsRes.data.applications.slice(0, 5)); }
        }
      } catch {
        // 403/404 = not an employee — section stays hidden
      } finally {
        if (!cancelled) { setHrLoading(false); }
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const handleCancelLeave = async (applicationId: string) => {
    setCancellingId(applicationId);
    try {
      await cancelLeave(applicationId);
      setLeaveApps(prev => prev.map(a => a.id === applicationId ? {...a, status: 'cancelled'} : a));
    } catch { /* silently ignore */ }
    finally { setCancellingId(null); }
  };

  if (!user) { return null; }

  const initials = user.name.split(' ').map(n => n[0]).join('').toUpperCase();
  const roleDisplay = user.role.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const deptDisplay = user.department.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const hasEmployee = !!leaveBalance;

  const statusColor = (s: string) => {
    if (s === 'approved') { return colors.success; }
    if (s === 'rejected') { return colors.danger; }
    if (s === 'cancelled') { return colors.textDim; }
    return colors.warning; // pending
  };

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
          <Text style={[styles.roleLabel, {color: colors.textMuted}]}>
            {user.role.replace(/_/g, ' ').toUpperCase()}
          </Text>
          <DeptBadge dept={user.department} />
        </View>

        {/* Info Card */}
        <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <InfoRow icon="mail-outline" label="Email" value={user.email} colors={colors} />
          <InfoRow icon="briefcase-outline" label="Role" value={roleDisplay} colors={colors} />
          <InfoRow icon="business-outline" label="Department" value={deptDisplay} colors={colors} />
        </View>

        {/* Employee Section — only if user has a linked active employee record */}
        {!hrLoading && hasEmployee && leaveBalance && (
          <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
            <Text style={[styles.sectionTitle, {color: colors.textMuted}]}>EMPLOYEE</Text>

            {/* Leave Balances */}
            <View style={styles.leaveBalanceRow}>
              {leaveBalance.balances.map((b, i) => (
                <View
                  key={i}
                  style={[styles.leaveBalanceCard, {backgroundColor: colors.surface, borderColor: colors.border}]}>
                  <Text style={[styles.leaveBalanceNum, {color: colors.accent}]}>{b.remaining ?? 0}</Text>
                  <Text style={[styles.leaveBalanceLabel, {color: colors.textDim}]}>
                    {(b.leave_type_name ?? b.leave_type_id ?? 'Leave').split(' ')[0]}
                  </Text>
                  <Text style={[styles.leaveBalanceSub, {color: colors.textDim}]}>
                    {b.used ?? 0} used / {b.entitled ?? 0} total
                  </Text>
                </View>
              ))}
            </View>

            {/* Apply Leave button */}
            <TouchableOpacity
              onPress={() => navigation.navigate('LeaveApplication', {employee_id: leaveBalance.employee_id})}
              activeOpacity={0.8}
              style={[styles.applyBtn, {backgroundColor: colors.accentSoft, borderColor: colors.accent + '44'}]}>
              <Icon name="calendar-outline" size={16} color={colors.accent} />
              <Text style={[styles.applyBtnText, {color: colors.accent}]}>Apply Leave</Text>
            </TouchableOpacity>

            {/* Recent Leave Applications */}
            {leaveApps.length > 0 && (
              <>
                <View style={[styles.divider, {borderColor: colors.border}]} />
                <Text style={[styles.subSectionTitle, {color: colors.textDim}]}>RECENT APPLICATIONS</Text>
                {leaveApps.map(app => (
                  <View key={app.id} style={styles.leaveAppRow}>
                    <View style={styles.leaveAppInfo}>
                      <Text style={[styles.leaveAppType, {color: colors.text}]}>
                        {app.leave_type_name ?? 'Leave'} · {app.total_days}d
                      </Text>
                      <Text style={[styles.leaveAppDates, {color: colors.textMuted}]}>
                        {app.start_date} → {app.end_date}
                      </Text>
                    </View>
                    <View style={styles.leaveAppRight}>
                      <View style={[styles.statusBadge, {backgroundColor: statusColor(app.status) + '20'}]}>
                        <Text style={[styles.statusText, {color: statusColor(app.status)}]}>
                          {app.status}
                        </Text>
                      </View>
                      {app.status === 'pending' && (
                        <TouchableOpacity
                          onPress={() => handleCancelLeave(app.id)}
                          disabled={cancellingId === app.id}
                          style={styles.cancelBtn}>
                          <Text style={[styles.cancelBtnText, {color: colors.danger}]}>
                            {cancellingId === app.id ? '…' : 'Cancel'}
                          </Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                ))}
              </>
            )}
          </View>
        )}

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
  avatarSection: {alignItems: 'center', paddingVertical: 32, gap: 8},
  avatarLarge: {
    width: 88,
    height: 88,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  avatarText: {fontSize: 36, fontWeight: '800', color: '#fff'},
  userName: {fontSize: 22, fontWeight: '800'},
  roleLabel: {fontSize: 11, fontWeight: '700', letterSpacing: 1, textAlign: 'center'},
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
  // Employee section
  leaveBalanceRow: {flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingVertical: 12},
  leaveBalanceCard: {
    flex: 1, alignItems: 'center', padding: 12, borderRadius: 12, borderWidth: 1,
  },
  leaveBalanceNum: {fontSize: 22, fontWeight: '800'},
  leaveBalanceLabel: {fontSize: 11, fontWeight: '600', marginTop: 2},
  leaveBalanceSub: {fontSize: 10, marginTop: 2, textAlign: 'center'},
  applyBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, marginHorizontal: 16, marginBottom: 12,
    paddingVertical: 10, borderRadius: 10, borderWidth: 1,
  },
  applyBtnText: {fontSize: 14, fontWeight: '600'},
  divider: {borderTopWidth: StyleSheet.hairlineWidth, marginHorizontal: 16, marginBottom: 8},
  subSectionTitle: {
    fontSize: 10, fontWeight: '700', letterSpacing: 0.8,
    paddingHorizontal: 16, paddingBottom: 6,
  },
  leaveAppRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 10, gap: 8,
  },
  leaveAppInfo: {flex: 1},
  leaveAppType: {fontSize: 13, fontWeight: '600'},
  leaveAppDates: {fontSize: 11, marginTop: 2},
  leaveAppRight: {alignItems: 'flex-end', gap: 4},
  statusBadge: {paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6},
  statusText: {fontSize: 11, fontWeight: '600', textTransform: 'capitalize'},
  cancelBtn: {paddingHorizontal: 4},
  cancelBtnText: {fontSize: 12, fontWeight: '600'},
});
