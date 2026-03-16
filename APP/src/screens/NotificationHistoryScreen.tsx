import React, {useEffect, useCallback} from 'react';
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {useNotificationStore} from '../stores/notificationStore';
import {NotificationRecord} from '../api/notificationsApi';

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const diff = Math.floor((now - new Date(iso).getTime()) / 1000);
  if (diff < 60) { return 'Just now'; }
  if (diff < 3600) { return `${Math.floor(diff / 60)}m ago`; }
  if (diff < 86400) { return `${Math.floor(diff / 3600)}h ago`; }
  if (diff < 172800) { return 'Yesterday'; }
  return new Date(iso).toLocaleDateString();
}

type CardProps = {
  item: NotificationRecord;
  colors: ReturnType<typeof useTheme>;
};

const NotificationCard: React.FC<CardProps> = ({item, colors}) => (
  <View style={[styles.card, {backgroundColor: colors.surface, borderColor: colors.border}]}>
    <View style={[styles.iconWrap, {backgroundColor: colors.accentSoft}]}>
      <Icon name="notifications-outline" size={20} color={colors.accent} />
    </View>
    <View style={styles.cardBody}>
      <View style={styles.cardTop}>
        <Text style={[styles.cardTitle, {color: colors.text}]} numberOfLines={1}>
          {item.title}
        </Text>
        <Text style={[styles.cardTime, {color: colors.textDim}]}>
          {formatRelativeTime(item.sent_at)}
        </Text>
      </View>
      <Text style={[styles.cardBodyText, {color: colors.textMuted}]} numberOfLines={2}>
        {item.body}
      </Text>
    </View>
  </View>
);

export const NotificationHistoryScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const {notifications, loading, loadNotifications} = useNotificationStore();
  const colors = useTheme();

  useEffect(() => {
    loadNotifications();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const renderItem = useCallback(
    ({item}: {item: NotificationRecord}) => <NotificationCard item={item} colors={colors} />,
    [colors],
  );

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.title, {color: colors.text}]}>Notification History</Text>
      </View>

      <FlatList
        data={notifications}
        keyExtractor={item => item.id}
        renderItem={renderItem}
        contentContainerStyle={notifications.length === 0 ? styles.emptyContainer : styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={loadNotifications}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyWrap}>
              <Icon name="notifications-outline" size={48} color={colors.textDim} />
              <Text style={[styles.emptyText, {color: colors.textDim}]}>
                No notifications yet
              </Text>
            </View>
          ) : null
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {padding: 8},
  title: {fontSize: 18, fontWeight: '700', marginLeft: 4},
  listContent: {padding: 16, gap: 10},
  emptyContainer: {flex: 1},
  emptyWrap: {flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80, gap: 12},
  emptyText: {fontSize: 15},
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  cardBody: {flex: 1, gap: 4},
  cardTop: {flexDirection: 'row', alignItems: 'center', gap: 8},
  cardTitle: {flex: 1, fontSize: 14, fontWeight: '700'},
  cardTime: {fontSize: 12},
  cardBodyText: {fontSize: 13, lineHeight: 18},
});
