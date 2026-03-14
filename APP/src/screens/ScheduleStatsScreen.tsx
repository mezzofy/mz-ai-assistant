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
import {useSchedulerStore} from '../stores/schedulerStore';
import {ScheduledJob} from '../api/schedulerApi';

function formatNextRun(iso: string | null): string {
  if (!iso) { return '—'; }
  const d = new Date(iso);
  if (isNaN(d.getTime())) { return '—'; }
  return d.toLocaleString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function formatDelivery(deliver_to: ScheduledJob['deliver_to']): string {
  if (deliver_to.teams_channel) { return deliver_to.teams_channel; }
  if (deliver_to.email && deliver_to.email.length > 0) {
    return deliver_to.email.join(', ');
  }
  return 'Personal folder';
}

type JobCardProps = {
  job: ScheduledJob;
  colors: ReturnType<typeof useTheme>;
};

const JobCard: React.FC<JobCardProps> = ({job, colors}) => (
  <View style={[styles.card, {backgroundColor: colors.surface, borderColor: colors.border}]}>
    <View style={styles.cardHeader}>
      <Text style={[styles.jobName, {color: colors.text}]} numberOfLines={1}>
        {job.name}
      </Text>
      <View style={[styles.badge, {backgroundColor: colors.accent + '22'}]}>
        <Text style={[styles.badgeText, {color: colors.accent}]}>
          {job.agent.charAt(0).toUpperCase() + job.agent.slice(1)}
        </Text>
      </View>
    </View>

    <View style={styles.statusRow}>
      <View style={[styles.dot, {backgroundColor: job.is_active ? '#4CAF50' : colors.textDim}]} />
      <Text style={[styles.statusText, {color: job.is_active ? '#4CAF50' : colors.textDim}]}>
        {job.is_active ? 'Active' : 'Inactive'}
      </Text>
    </View>

    <View style={styles.metaRow}>
      <Icon name="calendar-outline" size={13} color={colors.textMuted} />
      <Text style={[styles.metaLabel, {color: colors.textMuted}]}>Next trigger: </Text>
      <Text style={[styles.metaValue, {color: colors.text}]}>{formatNextRun(job.next_run)}</Text>
    </View>

    <View style={styles.metaRow}>
      <Icon name="code-outline" size={13} color={colors.textMuted} />
      <Text style={[styles.scheduleText, {color: colors.textDim}]}>{job.schedule}</Text>
    </View>

    <Text style={[styles.message, {color: colors.textMuted}]} numberOfLines={2}>
      {job.message}
    </Text>

    <View style={[styles.deliveryRow, {borderTopColor: colors.border}]}>
      <Icon name="send-outline" size={13} color={colors.textMuted} />
      <Text style={[styles.deliveryText, {color: colors.textMuted}]}>
        {formatDelivery(job.deliver_to)}
      </Text>
    </View>
  </View>
);

export const ScheduleStatsScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const {jobs, loading, loadJobs} = useSchedulerStore();
  const colors = useTheme();

  useEffect(() => {
    loadJobs();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const renderJob = useCallback(
    ({item}: {item: ScheduledJob}) => <JobCard job={item} colors={colors} />,
    [colors],
  );

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.title, {color: colors.text}]}>Scheduled Tasks</Text>
      </View>

      <FlatList
        data={jobs}
        keyExtractor={item => item.id}
        renderItem={renderJob}
        contentContainerStyle={jobs.length === 0 ? styles.emptyContainer : styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={loadJobs}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyWrap}>
              <Icon name="calendar-outline" size={48} color={colors.textDim} />
              <Text style={[styles.emptyText, {color: colors.textDim}]}>
                No scheduled tasks yet
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
  listContent: {padding: 16, gap: 12},
  emptyContainer: {flex: 1},
  emptyWrap: {flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80, gap: 12},
  emptyText: {fontSize: 15},
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    gap: 8,
  },
  cardHeader: {flexDirection: 'row', alignItems: 'center', gap: 10},
  jobName: {flex: 1, fontSize: 15, fontWeight: '700'},
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 20,
  },
  badgeText: {fontSize: 11, fontWeight: '700'},
  statusRow: {flexDirection: 'row', alignItems: 'center', gap: 6},
  dot: {width: 7, height: 7, borderRadius: 4},
  statusText: {fontSize: 12, fontWeight: '600'},
  metaRow: {flexDirection: 'row', alignItems: 'center', gap: 6},
  metaLabel: {fontSize: 12},
  metaValue: {fontSize: 12, fontWeight: '500'},
  scheduleText: {fontSize: 11, fontFamily: 'monospace'},
  message: {fontSize: 13, lineHeight: 19},
  deliveryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 2,
  },
  deliveryText: {fontSize: 12},
});
