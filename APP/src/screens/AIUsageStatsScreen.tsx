import React, {useCallback, useEffect, useState} from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {getSystemHealth, SystemHealth} from '../api/admin';

type StatusPillProps = {label: string; ok: boolean; colors: ReturnType<typeof useTheme>};

const StatusPill: React.FC<StatusPillProps> = ({label, ok, colors}) => (
  <View style={[styles.pill, {backgroundColor: ok ? colors.accent + '18' : colors.danger + '18'}]}>
    <View style={[styles.pillDot, {backgroundColor: ok ? colors.accent : colors.danger}]} />
    <Text style={[styles.pillText, {color: ok ? colors.accent : colors.danger}]}>
      {label}
    </Text>
  </View>
);

type ModelRowProps = {
  name: string;
  detail: string;
  role: string;
  online: boolean;
  colors: ReturnType<typeof useTheme>;
};

const ModelRow: React.FC<ModelRowProps> = ({name, detail, role, online, colors}) => (
  <View style={[styles.modelRow, {borderBottomColor: colors.border + '40'}]}>
    <View style={[styles.modelIcon, {backgroundColor: colors.accentSoft}]}>
      <Icon name="hardware-chip-outline" size={18} color={colors.accent} />
    </View>
    <View style={styles.modelInfo}>
      <Text style={[styles.modelName, {color: colors.text}]}>{name}</Text>
      <Text style={[styles.modelDetail, {color: colors.textMuted}]}>{detail}</Text>
    </View>
    <View style={styles.modelRight}>
      <Text style={[styles.modelRole, {color: colors.textDim}]}>{role}</Text>
      <View style={[styles.statusDot, {backgroundColor: online ? colors.accent : colors.danger}]} />
    </View>
  </View>
);

export const AIUsageStatsScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const colors = useTheme();
  const [health, setHealth] = useState<SystemHealth | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    const result = await getSystemHealth();
    setHealth(result); // null = 403 / error; SystemHealth = success
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const llmOk = health?.services.llm_manager === 'ok';
  const dbOk = health?.services.database === 'ok';
  const redisOk = health?.services.redis === 'ok';

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.title, {color: colors.text}]}>AI Usage Stats</Text>
        <TouchableOpacity onPress={fetchHealth} style={styles.refreshBtn} disabled={loading}>
          {loading
            ? <ActivityIndicator size="small" color={colors.accent} />
            : <Icon name="refresh-outline" size={22} color={colors.accent} />}
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.list} contentContainerStyle={{paddingBottom: 32}}>

        {/* AI Models */}
        <Text style={[styles.sectionLabel, {color: colors.textDim}]}>AI MODELS</Text>
        <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <ModelRow
            name="Claude Sonnet"
            detail="claude-sonnet-4-6 · Anthropic"
            role="Primary"
            online={health !== undefined && llmOk}
            colors={colors}
          />
          <ModelRow
            name="Kimi"
            detail="Moonshot AI · APAC fallback"
            role="Fallback"
            online={false}
            colors={colors}
          />
        </View>

        {/* System Status */}
        <Text style={[styles.sectionLabel, {color: colors.textDim}]}>SYSTEM STATUS</Text>
        <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          {health === null ? (
            <View style={styles.noAccess}>
              <Icon name="lock-closed-outline" size={20} color={colors.textMuted} />
              <Text style={[styles.noAccessText, {color: colors.textMuted}]}>
                Admin access required to view system status.
              </Text>
            </View>
          ) : health === undefined || loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={[styles.loadingText, {color: colors.textMuted}]}>Checking status…</Text>
            </View>
          ) : (
            <>
              <View style={styles.statusRow}>
                <Text style={[styles.statusLabel, {color: colors.text}]}>Database</Text>
                <StatusPill label={dbOk ? 'Online' : 'Unavailable'} ok={dbOk} colors={colors} />
              </View>
              <View style={[styles.statusRow, {borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border + '40'}]}>
                <Text style={[styles.statusLabel, {color: colors.text}]}>Redis Cache</Text>
                <StatusPill label={redisOk ? 'Online' : 'Unavailable'} ok={redisOk} colors={colors} />
              </View>
              <View style={[styles.statusRow, {borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border + '40'}]}>
                <Text style={[styles.statusLabel, {color: colors.text}]}>LLM Manager</Text>
                <StatusPill label={llmOk ? 'Online' : 'Not Initialized'} ok={llmOk} colors={colors} />
              </View>
              <View style={[styles.statusRow, {borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border + '40'}]}>
                <Text style={[styles.statusLabel, {color: colors.text}]}>Overall</Text>
                <StatusPill
                  label={health.status === 'ok' ? 'Healthy' : 'Degraded'}
                  ok={health.status === 'ok'}
                  colors={colors}
                />
              </View>
            </>
          )}
        </View>

        {/* Usage Stats */}
        <Text style={[styles.sectionLabel, {color: colors.textDim}]}>USAGE STATS</Text>
        <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <View style={styles.comingSoon}>
            <Icon name="bar-chart-outline" size={28} color={colors.textMuted} />
            <Text style={[styles.comingSoonTitle, {color: colors.text}]}>Coming Soon</Text>
            <Text style={[styles.comingSoonSub, {color: colors.textMuted}]}>
              Token usage, model breakdown, and cost estimates will appear here.
            </Text>
          </View>
        </View>

      </ScrollView>
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
  title: {flex: 1, fontSize: 18, fontWeight: '700', marginLeft: 4},
  refreshBtn: {padding: 8, width: 40, alignItems: 'center'},
  list: {flex: 1, paddingHorizontal: 16},
  sectionLabel: {fontSize: 11, fontWeight: '700', letterSpacing: 0.8, marginTop: 20, marginBottom: 8, marginLeft: 4},
  card: {borderRadius: 14, overflow: 'hidden', borderWidth: 1, marginBottom: 4},
  // Model rows
  modelRow: {flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderBottomWidth: StyleSheet.hairlineWidth},
  modelIcon: {width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center'},
  modelInfo: {flex: 1},
  modelName: {fontSize: 14, fontWeight: '600'},
  modelDetail: {fontSize: 12, marginTop: 2},
  modelRight: {alignItems: 'flex-end', gap: 6},
  modelRole: {fontSize: 11, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5},
  statusDot: {width: 8, height: 8, borderRadius: 4},
  // Status rows
  statusRow: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12},
  statusLabel: {fontSize: 14, fontWeight: '500'},
  // Pill
  pill: {flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20},
  pillDot: {width: 6, height: 6, borderRadius: 3},
  pillText: {fontSize: 12, fontWeight: '600'},
  // States
  noAccess: {flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16},
  noAccessText: {flex: 1, fontSize: 13},
  loadingRow: {flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16},
  loadingText: {fontSize: 13},
  // Coming soon
  comingSoon: {alignItems: 'center', padding: 28, gap: 8},
  comingSoonTitle: {fontSize: 15, fontWeight: '700'},
  comingSoonSub: {fontSize: 13, textAlign: 'center', lineHeight: 18},
});
