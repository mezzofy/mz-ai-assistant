import React, {useState, useEffect, useCallback} from 'react';
import {
  View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator,
  RefreshControl,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {useChatStore} from '../stores/chatStore';
import type {SessionSummary, TaskSummary} from '../api/chat';

const formatSessionDate = (iso: string): string => {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) {
    return `Today, ${d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`;
  }
  if (d.toDateString() === yesterday.toDateString()) {
    return 'Yesterday';
  }
  return d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
};

// Custom title takes priority over last_message content.
const getSessionTitle = (s: SessionSummary, titles: Record<string, string>): string => {
  if (titles[s.session_id]) {
    return titles[s.session_id];
  }
  if (s.last_message?.content) {
    const content = s.last_message.content.trim();
    return content.length > 50 ? `${content.slice(0, 50)}…` : content;
  }
  return `Session ${s.session_id.slice(0, 8)}`;
};

const getTaskStatusColor = (status: TaskSummary['status'], colors: any): string => {
  switch (status) {
    case 'queued':    return colors.info;
    case 'running':   return colors.warning;
    case 'completed': return colors.success;
    case 'failed':    return colors.danger;
    case 'cancelled': return colors.textDim;
    default:          return colors.textDim;
  }
};

type FilterType = 'active' | 'favorites' | 'archived';

export const HistoryScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const {sessions, loadSessions, loadHistory, sessionTitles, loadTitles, tasks, loadTasks,
         toggleFavorite, toggleArchive} = useChatStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<FilterType>('active');
  const colors = useTheme();

  useEffect(() => {
    loadTitles();
    Promise.all([loadSessions(), loadTasks()]).finally(() => setLoading(false));
  }, [loadSessions, loadTasks, loadTitles]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([loadSessions(), loadTasks()]);
    setRefreshing(false);
  }, [loadSessions, loadTasks]);

  // loadHistory sets messages + sessionId in chatStore, then navigate to Chat tab.
  // loadHistory swallows errors internally — navigation happens regardless.
  const handleSessionTap = useCallback(
    (sessionId: string) => {
      loadHistory(sessionId).then(() => {
        navigation.navigate('Chat');
      });
    },
    [loadHistory, navigation],
  );

  const filterBase = sessions.filter(s => {
    if (activeFilter === 'active')    { return !s.is_archived; }
    if (activeFilter === 'favorites') { return s.is_favorite && !s.is_archived; }
    if (activeFilter === 'archived')  { return s.is_archived; }
    return true;
  });

  const filtered = query
    ? filterBase.filter(s => {
        const title = getSessionTitle(s, sessionTitles).toLowerCase();
        const preview = (s.last_message?.content ?? '').toLowerCase();
        return title.includes(query.toLowerCase()) || preview.includes(query.toLowerCase());
      })
    : filterBase;

  const tasksBySession = tasks.reduce<Record<string, TaskSummary[]>>((acc, t) => {
    if (t.session_id) {
      acc[t.session_id] = acc[t.session_id] ? [...acc[t.session_id], t] : [t];
    }
    return acc;
  }, {});

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      <View style={[styles.header, {flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center'}]}>
        <View>
          <Text style={[styles.title, {color: colors.text}]}>Chat History</Text>
          <Text style={[styles.count, {color: colors.textMuted}]}>{filtered.length} {activeFilter} conversations</Text>
        </View>
        <TouchableOpacity onPress={handleRefresh} disabled={refreshing} style={{padding: 8}}>
          {refreshing
            ? <ActivityIndicator size="small" color={colors.accent} />
            : <Icon name="refresh-outline" size={22} color={colors.accent} />}
        </TouchableOpacity>
      </View>

      <View style={[styles.searchWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
        <Icon name="search-outline" size={16} color={colors.textDim} style={styles.searchIcon} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search conversations..."
          placeholderTextColor={colors.textDim}
          style={[styles.searchInput, {color: colors.text}]}
        />
      </View>

      <View style={styles.filterRow}>
        {(['active', 'favorites', 'archived'] as FilterType[]).map(f => (
          <TouchableOpacity
            key={f}
            style={[
              styles.filterPill,
              {borderColor: colors.border},
              activeFilter === f && {backgroundColor: colors.accent, borderColor: colors.accent},
            ]}
            onPress={() => setActiveFilter(f)}>
            <Text
              style={[
                styles.filterPillText,
                {color: activeFilter === f ? '#fff' : colors.textMuted},
              ]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : filtered.length === 0 ? (
        <View style={styles.center}>
          <Icon name="chatbubbles-outline" size={40} color={colors.textDim} />
          <Text style={[styles.emptyText, {color: colors.textDim}]}>
            {query ? 'No matching conversations' :
             activeFilter === 'favorites' ? 'No favorited conversations' :
             activeFilter === 'archived' ? 'No archived conversations' :
             'No chat history yet'}
          </Text>
        </View>
      ) : (
        <ScrollView
          style={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
              colors={[colors.accent]}
            />
          }>
          {filtered.map(s => (
            <TouchableOpacity
              key={s.session_id}
              style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}
              activeOpacity={0.7}
              onPress={() => handleSessionTap(s.session_id)}>
              <View style={styles.cardTop}>
                <Text style={[styles.cardTitle, {color: colors.text}]} numberOfLines={1}>
                  {getSessionTitle(s, sessionTitles)}
                </Text>
                <View style={styles.cardActions}>
                  <TouchableOpacity
                    onPress={() => toggleFavorite(s.session_id)}
                    hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                    <Icon
                      name={s.is_favorite ? 'star' : 'star-outline'}
                      size={16}
                      color={s.is_favorite ? colors.warning : colors.textDim}
                    />
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => toggleArchive(s.session_id)}
                    hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}
                    style={styles.archiveBtn}>
                    <Icon
                      name={s.is_archived ? 'arrow-undo-outline' : 'archive-outline'}
                      size={15}
                      color={colors.textDim}
                    />
                  </TouchableOpacity>
                  <Icon name="chevron-forward" size={16} color={colors.textDim} />
                </View>
              </View>
              {s.last_message ? (
                <Text style={[styles.cardPreview, {color: colors.textMuted}]} numberOfLines={2}>
                  {s.last_message.content}
                </Text>
              ) : null}
              <View style={styles.cardBottom}>
                <Text style={[styles.cardTime, {color: colors.textDim}]}>{formatSessionDate(s.updated_at)}</Text>
                <Text style={[styles.cardMsgs, {color: colors.accent}]}>{s.message_count} messages</Text>
              </View>
              {(tasksBySession[s.session_id] ?? []).filter(t => t.queue_name === 'background').length > 0 && (
                <View style={styles.taskRow}>
                  {tasksBySession[s.session_id]
                    .filter(t => t.queue_name === 'background')
                    .map(t => {
                      const c = getTaskStatusColor(t.status, colors);
                      return (
                        <View
                          key={t.id}
                          style={[
                            styles.taskBadge,
                            {backgroundColor: c + '22', borderColor: c + '55'},
                          ]}>
                          <Text style={[styles.taskBadgeText, {color: c}]}>
                            {'Task ID: '}{t.id.slice(0, 8).toUpperCase()}{'  '}{t.status.toUpperCase()}
                          </Text>
                        </View>
                      );
                    })}
                </View>
              )}
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {padding: 16, paddingBottom: 8},
  title: {fontSize: 20, fontWeight: '800'},
  count: {fontSize: 12, marginTop: 2},
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  searchIcon: {paddingLeft: 14},
  searchInput: {flex: 1, padding: 12, paddingLeft: 10, fontSize: 14},
  center: {flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12},
  emptyText: {fontSize: 14},
  list: {flex: 1, paddingHorizontal: 16},
  card: {
    padding: 14,
    paddingHorizontal: 16,
    borderRadius: 14,
    marginBottom: 8,
    borderWidth: 1,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  cardTitle: {flex: 1, fontSize: 14, fontWeight: '700', marginRight: 8},
  cardPreview: {fontSize: 13, lineHeight: 18, marginTop: 4},
  cardBottom: {flexDirection: 'row', justifyContent: 'space-between', marginTop: 8},
  cardTime: {fontSize: 11},
  cardMsgs: {fontSize: 11},
  taskRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 8,
  },
  taskBadge: {
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  taskBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  filterRow: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  filterPill: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  filterPillText: {
    fontSize: 12,
    fontWeight: '600',
  },
  cardActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  archiveBtn: {},
});
