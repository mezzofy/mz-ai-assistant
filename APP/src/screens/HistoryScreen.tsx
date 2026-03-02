import React, {useState, useEffect, useCallback} from 'react';
import {
  View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {useChatStore} from '../stores/chatStore';
import type {SessionSummary} from '../api/chat';

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

export const HistoryScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const {sessions, loadSessions, loadHistory, sessionTitles, loadTitles} = useChatStore();
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const colors = useTheme();

  useEffect(() => {
    loadTitles();
    loadSessions().finally(() => setLoading(false));
  }, [loadSessions, loadTitles]);

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

  const filtered = query
    ? sessions.filter(s => {
        const title = getSessionTitle(s, sessionTitles).toLowerCase();
        const preview = (s.last_message?.content ?? '').toLowerCase();
        return title.includes(query.toLowerCase()) || preview.includes(query.toLowerCase());
      })
    : sessions;

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      <View style={styles.header}>
        <Text style={[styles.title, {color: colors.text}]}>Chat History</Text>
        <Text style={[styles.count, {color: colors.textMuted}]}>{filtered.length} conversations</Text>
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

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : filtered.length === 0 ? (
        <View style={styles.center}>
          <Icon name="chatbubbles-outline" size={40} color={colors.textDim} />
          <Text style={[styles.emptyText, {color: colors.textDim}]}>
            {query ? 'No matching conversations' : 'No chat history yet'}
          </Text>
        </View>
      ) : (
        <ScrollView style={styles.list}>
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
                <Icon name="chevron-forward" size={16} color={colors.textDim} />
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
});
