import React, {useState, useCallback} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
  Alert,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {
  getPendingApprovals,
  updateLeaveStatus,
  type PendingApproval,
} from '../api/hrApi';

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
  } catch {
    return dateStr;
  }
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function initials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map(w => w[0] || '')
    .join('')
    .toUpperCase();
}

type Props = {navigation: any};

export function LeaveApprovalScreen({navigation}: Props) {
  const colors = useTheme();

  const [items, setItems] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reject modal state
  const [rejectModal, setRejectModal] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<PendingApproval | null>(null);
  const [rejectComment, setRejectComment] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null); // application_id being actioned

  const fetchApprovals = useCallback(async () => {
    try {
      const res = await getPendingApprovals();
      setItems(res.data?.pending_approvals ?? []);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Failed to load approvals');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchApprovals();
  }, [fetchApprovals]);

  const handleApprove = async (item: PendingApproval) => {
    setActionLoading(item.id);
    try {
      await updateLeaveStatus(item.id, 'approved');
      setItems(prev => prev.filter(i => i.id !== item.id));
    } catch (e: any) {
      Alert.alert('Error', e?.message || 'Failed to approve leave');
    } finally {
      setActionLoading(null);
    }
  };

  const openRejectModal = (item: PendingApproval) => {
    setRejectTarget(item);
    setRejectComment('');
    setRejectModal(true);
  };

  const handleRejectConfirm = async () => {
    if (!rejectTarget) return;
    setActionLoading(rejectTarget.id);
    setRejectModal(false);
    try {
      await updateLeaveStatus(rejectTarget.id, 'rejected', rejectComment.trim() || undefined);
      setItems(prev => prev.filter(i => i.id !== rejectTarget.id));
    } catch (e: any) {
      Alert.alert('Error', e?.message || 'Failed to reject leave');
    } finally {
      setActionLoading(null);
      setRejectTarget(null);
      setRejectComment('');
    }
  };

  const s = styles(colors);

  const renderItem = ({item}: {item: PendingApproval}) => {
    const isActioning = actionLoading === item.id;
    const days = item.total_days === 1 ? '1 day' : `${item.total_days} days`;

    return (
      <View style={s.card}>
        {/* Employee row */}
        <View style={s.empRow}>
          <View style={s.avatar}>
            <Text style={s.avatarText}>{initials(item.employee_name)}</Text>
          </View>
          <View style={s.empInfo}>
            <Text style={s.empName}>{item.employee_name}</Text>
            <Text style={s.empMeta}>{item.staff_id}{item.department ? ` · ${item.department}` : ''}</Text>
          </View>
          <Text style={s.timeAgo}>{timeAgo(item.created_at)}</Text>
        </View>

        {/* Leave details */}
        <View style={s.detailsRow}>
          <View style={s.badge}>
            <Text style={s.badgeText}>{item.leave_type_name}</Text>
          </View>
          <Text style={s.dateRange}>
            {formatDate(item.start_date)} – {formatDate(item.end_date)}
          </Text>
          <Text style={s.daysLabel}>{days}</Text>
        </View>

        {/* Reason */}
        {item.reason ? (
          <Text style={s.reason} numberOfLines={2}>{item.reason}</Text>
        ) : null}

        {/* Manager name (admin view) */}
        {item.manager_name ? (
          <Text style={s.managerNote}>
            <Text style={s.managerLabel}>Manager: </Text>{item.manager_name}
          </Text>
        ) : null}

        {/* Action buttons */}
        <View style={s.actions}>
          <TouchableOpacity
            style={[s.rejectBtn, isActioning && s.btnDisabled]}
            onPress={() => openRejectModal(item)}
            disabled={isActioning}>
            {isActioning ? (
              <ActivityIndicator size="small" color="#EF4444" />
            ) : (
              <>
                <Icon name="close-circle-outline" size={16} color="#EF4444" />
                <Text style={s.rejectBtnText}>Reject</Text>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.approveBtn, isActioning && s.btnDisabled]}
            onPress={() => handleApprove(item)}
            disabled={isActioning}>
            {isActioning ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Icon name="checkmark-circle-outline" size={16} color="#fff" />
                <Text style={s.approveBtnText}>Approve</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <View style={s.container}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={s.backBtn} hitSlop={{top: 8, left: 8, bottom: 8, right: 8}}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.title}>Leave Approvals</Text>
        <View style={s.countPill}>
          <Text style={s.countText}>{items.length}</Text>
        </View>
      </View>

      {/* Body */}
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : error ? (
        <View style={s.center}>
          <Icon name="alert-circle-outline" size={40} color={colors.textDim} />
          <Text style={s.errorText}>{error}</Text>
          <TouchableOpacity style={s.retryBtn} onPress={fetchApprovals}>
            <Text style={s.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={i => i.id}
          renderItem={renderItem}
          contentContainerStyle={items.length === 0 ? s.emptyContainer : s.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <View style={s.center}>
              <Icon name="checkmark-done-circle-outline" size={56} color={colors.textDim} />
              <Text style={s.emptyTitle}>All caught up!</Text>
              <Text style={s.emptySubtitle}>No pending leave approvals.</Text>
            </View>
          }
        />
      )}

      {/* Reject Modal */}
      <Modal
        visible={rejectModal}
        transparent
        animationType="fade"
        onRequestClose={() => setRejectModal(false)}>
        <View style={s.modalOverlay}>
          <View style={s.modalBox}>
            <Text style={s.modalTitle}>Reject Leave</Text>
            {rejectTarget && (
              <Text style={s.modalSubtitle}>
                {rejectTarget.employee_name} · {rejectTarget.leave_type_name} ·{' '}
                {rejectTarget.total_days === 1 ? '1 day' : `${rejectTarget.total_days} days`}
              </Text>
            )}
            <TextInput
              style={s.commentInput}
              placeholder="Optional comment for employee"
              placeholderTextColor={colors.textDim}
              value={rejectComment}
              onChangeText={setRejectComment}
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />
            <View style={s.modalActions}>
              <TouchableOpacity
                style={s.modalCancelBtn}
                onPress={() => setRejectModal(false)}>
                <Text style={s.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={s.modalRejectBtn}
                onPress={handleRejectConfirm}>
                <Text style={s.modalRejectText}>Confirm Reject</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = (c: ReturnType<typeof useTheme>) =>
  StyleSheet.create({
    container: {flex: 1, backgroundColor: c.primary},
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 16,
      paddingTop: 16,
      paddingBottom: 12,
      borderBottomWidth: 1,
      borderBottomColor: c.border,
      gap: 10,
    },
    backBtn: {padding: 4},
    title: {flex: 1, fontSize: 18, fontWeight: '700', color: c.text},
    countPill: {
      backgroundColor: c.accent + '22',
      borderRadius: 12,
      paddingHorizontal: 10,
      paddingVertical: 3,
    },
    countText: {fontSize: 13, fontWeight: '700', color: c.accent},
    center: {flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 32},
    emptyContainer: {flex: 1},
    listContent: {padding: 12, gap: 12},
    card: {
      backgroundColor: c.surface,
      borderRadius: 12,
      padding: 16,
      borderWidth: 1,
      borderColor: c.border,
      gap: 12,
    },
    empRow: {flexDirection: 'row', alignItems: 'center', gap: 10},
    avatar: {
      width: 38,
      height: 38,
      borderRadius: 19,
      backgroundColor: c.accent + '25',
      alignItems: 'center',
      justifyContent: 'center',
    },
    avatarText: {fontSize: 14, fontWeight: '700', color: c.accent},
    empInfo: {flex: 1},
    empName: {fontSize: 15, fontWeight: '600', color: c.text},
    empMeta: {fontSize: 12, color: c.textDim, marginTop: 1},
    timeAgo: {fontSize: 11, color: c.textDim},
    detailsRow: {flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap'},
    badge: {
      backgroundColor: c.accent + '20',
      borderRadius: 6,
      paddingHorizontal: 8,
      paddingVertical: 3,
    },
    badgeText: {fontSize: 12, fontWeight: '600', color: c.accent},
    dateRange: {fontSize: 13, color: c.text, flex: 1},
    daysLabel: {fontSize: 13, fontWeight: '600', color: c.text},
    reason: {fontSize: 13, color: c.textDim, fontStyle: 'italic'},
    managerNote: {fontSize: 12, color: c.textDim},
    managerLabel: {fontWeight: '600'},
    actions: {flexDirection: 'row', gap: 10, marginTop: 4},
    rejectBtn: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      paddingVertical: 10,
      borderRadius: 8,
      borderWidth: 1.5,
      borderColor: '#EF4444',
    },
    rejectBtnText: {fontSize: 14, fontWeight: '600', color: '#EF4444'},
    approveBtn: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      paddingVertical: 10,
      borderRadius: 8,
      backgroundColor: '#00D4AA',
    },
    approveBtnText: {fontSize: 14, fontWeight: '600', color: '#fff'},
    btnDisabled: {opacity: 0.5},
    errorText: {fontSize: 14, color: c.textDim, textAlign: 'center'},
    retryBtn: {
      paddingHorizontal: 20,
      paddingVertical: 8,
      borderRadius: 8,
      backgroundColor: c.accent,
    },
    retryText: {fontSize: 14, fontWeight: '600', color: '#fff'},
    emptyTitle: {fontSize: 17, fontWeight: '700', color: c.text},
    emptySubtitle: {fontSize: 14, color: c.textDim},
    // Modal
    modalOverlay: {
      flex: 1,
      backgroundColor: 'rgba(0,0,0,0.6)',
      justifyContent: 'center',
      alignItems: 'center',
      padding: 24,
    },
    modalBox: {
      backgroundColor: c.surface,
      borderRadius: 16,
      padding: 24,
      width: '100%',
      gap: 12,
    },
    modalTitle: {fontSize: 17, fontWeight: '700', color: c.text},
    modalSubtitle: {fontSize: 13, color: c.textDim},
    commentInput: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      padding: 12,
      fontSize: 14,
      color: c.text,
      minHeight: 80,
    },
    modalActions: {flexDirection: 'row', gap: 10, marginTop: 4},
    modalCancelBtn: {
      flex: 1,
      paddingVertical: 11,
      borderRadius: 8,
      borderWidth: 1,
      borderColor: c.border,
      alignItems: 'center',
    },
    modalCancelText: {fontSize: 14, fontWeight: '600', color: c.textDim},
    modalRejectBtn: {
      flex: 1,
      paddingVertical: 11,
      borderRadius: 8,
      backgroundColor: '#EF4444',
      alignItems: 'center',
    },
    modalRejectText: {fontSize: 14, fontWeight: '600', color: '#fff'},
  });
