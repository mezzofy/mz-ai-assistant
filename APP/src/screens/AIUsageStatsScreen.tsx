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
import {getSystemHealth, SystemHealth, checkModelStatus, ModelCheckResult} from '../api/admin';
import {getLlmUsageStats, LlmUsageStats} from '../api/llm';

function friendlyModelName(modelId: string): string {
  if (modelId.includes('claude')) return `Claude (${modelId})`;
  if (modelId.includes('moonshot') || modelId.includes('kimi')) return `Kimi (${modelId})`;
  return modelId;
}

type StatusPillProps = {label: string; ok: boolean; colors: ReturnType<typeof useTheme>};

const StatusPill: React.FC<StatusPillProps> = ({label, ok, colors}) => (
  <View style={[styles.pill, {backgroundColor: ok ? colors.success + '18' : colors.danger + '18'}]}>
    <View style={[styles.pillDot, {backgroundColor: ok ? colors.success : colors.danger}]} />
    <Text style={[styles.pillText, {color: ok ? colors.success : colors.danger}]}>
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
  onCheck?: () => void;
  checking?: boolean;
  checkResult?: ModelCheckResult | null;
};

const ModelRow: React.FC<ModelRowProps> = ({name, detail, role, online, colors, onCheck, checking, checkResult}) => (
  <View>
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
        <View style={styles.modelRightBottom}>
          <View style={[styles.statusDot, {backgroundColor: online ? colors.success : colors.danger}]} />
          {onCheck && (
            <TouchableOpacity onPress={onCheck} disabled={checking} style={styles.checkBtn}>
              {checking
                ? <ActivityIndicator size={14} color={colors.accent} />
                : <Icon name="pulse-outline" size={16} color={colors.accent} />}
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
    {checkResult && (
      <View style={[styles.checkResultRow, {borderBottomColor: colors.border + '40'}]}>
        <Text style={[
          styles.checkResultText,
          {color: checkResult.status === 'ok' ? colors.success : colors.danger},
        ]}>
          {checkResult.status === 'ok'
            ? `✓ Responded in ${checkResult.latency_ms}ms: ${checkResult.message}`
            : `✗ ${checkResult.message}`}
        </Text>
      </View>
    )}
  </View>
);

export const AIUsageStatsScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const colors = useTheme();
  const [health, setHealth] = useState<SystemHealth | null | undefined>(undefined);
  const [stats, setStats] = useState<LlmUsageStats | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [claudeCheck, setClaudeCheck] = useState<ModelCheckResult | null>(null);
  const [claudeChecking, setClaudeChecking] = useState(false);
  const [kimiCheck, setKimiCheck] = useState<ModelCheckResult | null>(null);
  const [kimiChecking, setKimiChecking] = useState(false);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setClaudeCheck(null);
    setKimiCheck(null);
    const [healthResult, statsResult] = await Promise.all([
      getSystemHealth(), // catches 403 internally — always resolves
      getLlmUsageStats().catch(() => null as LlmUsageStats | null),
    ]);
    setHealth(healthResult);
    setStats(statsResult);
    setLoading(false);
  }, []);

  const handleCheckClaude = useCallback(async () => {
    setClaudeChecking(true);
    const result = await checkModelStatus('claude');
    setClaudeCheck(result);
    setClaudeChecking(false);
  }, []);

  const handleCheckKimi = useCallback(async () => {
    setKimiChecking(true);
    const result = await checkModelStatus('kimi');
    setKimiCheck(result);
    setKimiChecking(false);
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
            detail={`${health?.model_names?.claude ?? 'claude-sonnet-4-6'} · Anthropic`}
            role="Primary"
            online={claudeCheck?.status === 'ok' ? true : (claudeCheck == null && health !== undefined && llmOk)}
            colors={colors}
            onCheck={handleCheckClaude}
            checking={claudeChecking}
            checkResult={claudeCheck}
          />
          <ModelRow
            name="Kimi"
            detail={`${health?.model_names?.kimi ?? 'moonshot-v1-8k'} · Moonshot AI`}
            role="Fallback"
            online={kimiCheck?.status === 'ok'}
            colors={colors}
            onCheck={handleCheckKimi}
            checking={kimiChecking}
            checkResult={kimiCheck}
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
          {stats === undefined || loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={[styles.loadingText, {color: colors.textMuted}]}>Loading stats…</Text>
            </View>
          ) : stats === null ? (
            <View style={styles.errorRow}>
              <Icon name="alert-circle-outline" size={20} color={colors.textMuted} />
              <Text style={[styles.errorText, {color: colors.textMuted}]}>Unable to load stats.</Text>
              <TouchableOpacity onPress={fetchHealth} style={styles.retryBtn}>
                <Text style={[styles.retryText, {color: colors.accent}]}>Retry</Text>
              </TouchableOpacity>
            </View>
          ) : stats.total_messages === 0 ? (
            <View style={styles.emptyRow}>
              <Icon name="bar-chart-outline" size={24} color={colors.textMuted} />
              <Text style={[styles.emptyText, {color: colors.textMuted}]}>No usage yet.</Text>
            </View>
          ) : (
            <>
              {/* Total messages */}
              <View style={styles.statRow}>
                <Text style={[styles.statLabel, {color: colors.text}]}>Messages</Text>
                <Text style={[styles.statValue, {color: colors.text}]}>
                  {stats.total_messages.toLocaleString()}
                </Text>
              </View>
              {/* Total tokens */}
              <View style={[styles.statRow, {borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border + '40'}]}>
                <View style={styles.statLabelGroup}>
                  <Text style={[styles.statLabel, {color: colors.text}]}>Total Tokens</Text>
                  <Text style={[styles.statSub, {color: colors.textMuted}]}>
                    {`In ${stats.total_input_tokens.toLocaleString()} · Out ${stats.total_output_tokens.toLocaleString()}`}
                  </Text>
                </View>
                <Text style={[styles.statValue, {color: colors.text}]}>
                  {(stats.total_input_tokens + stats.total_output_tokens).toLocaleString()}
                </Text>
              </View>
              {/* Per-model breakdown */}
              {stats.by_model.map(m => (
                <View
                  key={m.model}
                  style={[styles.modelUsageRow, {borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border + '40'}]}>
                  <View style={styles.modelUsageLeft}>
                    <Text style={[styles.modelUsageName, {color: colors.text}]}>{friendlyModelName(m.model)}</Text>
                    <Text style={[styles.modelUsageSub, {color: colors.textMuted}]}>
                      {`${m.count.toLocaleString()} msg · ${(m.input_tokens + m.output_tokens).toLocaleString()} tokens`}
                    </Text>
                  </View>
                  <View style={styles.modelUsageRight}>
                    <Text style={[styles.modelUsagePct, {color: colors.textDim}]}>
                      {`In ${m.input_tokens.toLocaleString()}`}
                    </Text>
                    <Text style={[styles.modelUsagePct, {color: colors.textDim}]}>
                      {`Out ${m.output_tokens.toLocaleString()}`}
                    </Text>
                  </View>
                </View>
              ))}
              {!stats.by_model.some(m => m.model.includes('moonshot') || m.model.includes('kimi')) && (
                <View
                  key="kimi-placeholder"
                  style={[styles.modelUsageRow, {borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border + '40'}]}>
                  <View style={styles.modelUsageLeft}>
                    <Text style={[styles.modelUsageName, {color: colors.text}]}>
                      {`Kimi (${health?.model_names?.kimi ?? 'moonshot-v1-8k'})`}
                    </Text>
                    <Text style={[styles.modelUsageSub, {color: colors.textMuted}]}>No usage yet</Text>
                  </View>
                </View>
              )}
            </>
          )}
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
  modelRight: {alignItems: 'flex-end', gap: 4},
  modelRole: {fontSize: 11, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5},
  modelRightBottom: {flexDirection: 'row', alignItems: 'center', gap: 8},
  statusDot: {width: 8, height: 8, borderRadius: 4},
  checkBtn: {padding: 2},
  checkResultRow: {paddingHorizontal: 14, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth},
  checkResultText: {fontSize: 12, fontWeight: '500'},
  // Status rows
  statusRow: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12},
  statusLabel: {fontSize: 14, fontWeight: '500'},
  // Pill
  pill: {flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20},
  pillDot: {width: 6, height: 6, borderRadius: 3},
  pillText: {fontSize: 12, fontWeight: '600'},
  // Shared states
  noAccess: {flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16},
  noAccessText: {flex: 1, fontSize: 13},
  loadingRow: {flexDirection: 'row', alignItems: 'center', gap: 10, padding: 16},
  loadingText: {fontSize: 13},
  // Error / empty
  errorRow: {flexDirection: 'row', alignItems: 'center', gap: 8, padding: 16},
  errorText: {flex: 1, fontSize: 13},
  retryBtn: {paddingHorizontal: 12, paddingVertical: 6},
  retryText: {fontSize: 13, fontWeight: '600'},
  emptyRow: {alignItems: 'center', padding: 28, gap: 8},
  emptyText: {fontSize: 13},
  // Usage stat rows
  statRow: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12},
  statLabelGroup: {flex: 1},
  statLabel: {fontSize: 14, fontWeight: '500'},
  statSub: {fontSize: 11, marginTop: 2},
  statValue: {fontSize: 16, fontWeight: '700', marginLeft: 8},
  // Per-model usage rows
  modelUsageRow: {flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12},
  modelUsageLeft: {flex: 1},
  modelUsageName: {fontSize: 13, fontWeight: '600'},
  modelUsageSub: {fontSize: 11, marginTop: 2},
  modelUsageRight: {alignItems: 'flex-end'},
  modelUsagePct: {fontSize: 11},
});
