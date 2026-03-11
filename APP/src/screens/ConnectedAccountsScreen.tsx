import React, {useCallback, useEffect, useState} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  Linking,
  StyleSheet,
  Alert,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {useMsStore} from '../stores/msStore';
import {getMsAuthUrlApi, postMsAuthCallbackApi} from '../api/msOAuth';

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseDeepLinkParams(url: string): Record<string, string> {
  const queryStart = url.indexOf('?');
  const hashStart = url.indexOf('#');
  const paramStr =
    queryStart !== -1
      ? url.slice(queryStart + 1, hashStart !== -1 ? hashStart : undefined)
      : hashStart !== -1
      ? url.slice(hashStart + 1)
      : '';
  const result: Record<string, string> = {};
  for (const part of paramStr.split('&')) {
    const [k, v] = part.split('=');
    if (k && v !== undefined) {
      result[decodeURIComponent(k)] = decodeURIComponent(v.replace(/\+/g, ' '));
    }
  }
  return result;
}

// ── Component ─────────────────────────────────────────────────────────────────

export const ConnectedAccountsScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const colors = useTheme();
  const {connected, msEmail, scopes, loading, error, loadStatus, disconnect, setConnected, clearError} =
    useMsStore();
  const [oauthLoading, setOauthLoading] = useState(false);
  const [savedState, setSavedState] = useState<string | null>(null);

  // Load status on mount
  useEffect(() => {
    loadStatus();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Deep link listener — receives msalauth://callback?code=...&state=...
  const handleDeepLink = useCallback(
    async ({url}: {url: string}) => {
      if (!url.startsWith('msalauth://')) {
        return;
      }
      const params = parseDeepLinkParams(url);
      const {code, state} = params;
      if (!code || !state) {
        setOauthLoading(false);
        return;
      }
      if (savedState && state !== savedState) {
        setOauthLoading(false);
        Alert.alert('Error', 'OAuth state mismatch. Please try again.');
        return;
      }
      try {
        const result = await postMsAuthCallbackApi(code, state);
        if (result.connected) {
          setConnected(result.ms_email, result.scopes, null);
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Connection failed. Please try again.';
        Alert.alert('Connection Failed', msg);
      } finally {
        setOauthLoading(false);
        setSavedState(null);
      }
    },
    [savedState, setConnected],
  );

  useEffect(() => {
    const sub = Linking.addEventListener('url', handleDeepLink);
    return () => sub.remove();
  }, [handleDeepLink]);

  // ── Connect flow ────────────────────────────────────────────────────────────

  const handleConnect = async () => {
    try {
      setOauthLoading(true);
      clearError();
      const {auth_url, state} = await getMsAuthUrlApi();
      setSavedState(state);
      await Linking.openURL(auth_url);
    } catch (e: unknown) {
      setOauthLoading(false);
      const msg = e instanceof Error ? e.message : 'Failed to start sign-in. Please try again.';
      Alert.alert('Error', msg);
    }
  };

  // ── Disconnect flow ─────────────────────────────────────────────────────────

  const handleDisconnect = () => {
    Alert.alert(
      'Disconnect Microsoft Account',
      `Remove ${msEmail ?? 'your Microsoft account'}? The AI will no longer be able to access your personal email, calendar, notes, or Teams.`,
      [
        {text: 'Cancel', style: 'cancel'},
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: async () => {
            try {
              await disconnect();
            } catch {
              Alert.alert('Error', 'Failed to disconnect. Please try again.');
            }
          },
        },
      ],
    );
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  const isLoading = loading || oauthLoading;

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.title, {color: colors.text}]}>Connected Accounts</Text>
      </View>

      <View style={styles.content}>
        {/* Microsoft Account Card */}
        <View style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <View style={styles.cardHeader}>
            <View style={[styles.msIcon, {backgroundColor: '#0078D4' + '18'}]}>
              <Icon name="logo-windows" size={24} color="#0078D4" />
            </View>
            <View style={styles.cardMeta}>
              <Text style={[styles.cardTitle, {color: colors.text}]}>Microsoft Account</Text>
              {connected && msEmail ? (
                <Text style={[styles.cardSubtitle, {color: colors.textMuted}]} numberOfLines={1}>
                  {msEmail}
                </Text>
              ) : (
                <Text style={[styles.cardSubtitle, {color: colors.textDim}]}>Not connected</Text>
              )}
            </View>
            {connected ? (
              <View style={[styles.statusDot, {backgroundColor: colors.success}]} />
            ) : (
              <View style={[styles.statusDot, {backgroundColor: colors.textDim}]} />
            )}
          </View>

          {/* Scope pills */}
          {connected && scopes.length > 0 && (
            <View style={styles.scopeRow}>
              {['Mail', 'Calendar', 'Notes', 'Teams'].map(label => (
                <View key={label} style={[styles.scopePill, {backgroundColor: colors.accentSoft}]}>
                  <Text style={[styles.scopeText, {color: colors.accent}]}>{label}</Text>
                </View>
              ))}
            </View>
          )}

          {/* Action button */}
          {isLoading ? (
            <ActivityIndicator color={colors.accent} style={styles.spinner} />
          ) : connected ? (
            <TouchableOpacity
              style={[styles.btn, styles.btnDanger, {borderColor: colors.danger}]}
              onPress={handleDisconnect}
              activeOpacity={0.8}>
              <Icon name="unlink-outline" size={16} color={colors.danger} />
              <Text style={[styles.btnText, {color: colors.danger}]}>Disconnect</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={[styles.btn, {backgroundColor: '#0078D4'}]}
              onPress={handleConnect}
              activeOpacity={0.8}>
              <Icon name="logo-windows" size={16} color="#fff" />
              <Text style={[styles.btnText, {color: '#fff'}]}>Connect Microsoft Account</Text>
            </TouchableOpacity>
          )}

          {error ? (
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          ) : null}
        </View>

        {/* Info note */}
        <View style={[styles.infoBox, {backgroundColor: colors.surface, borderColor: colors.border}]}>
          <Icon name="information-circle-outline" size={16} color={colors.textMuted} />
          <Text style={[styles.infoText, {color: colors.textMuted}]}>
            Connecting your Microsoft account lets the AI read and send your personal emails, manage
            calendar events, access OneNote, and chat in Teams on your behalf.
          </Text>
        </View>
      </View>
    </View>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 12,
    gap: 4,
  },
  backBtn: {padding: 8},
  title: {fontSize: 18, fontWeight: '700'},
  content: {flex: 1, paddingHorizontal: 16, paddingTop: 8},
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 18,
    marginBottom: 14,
  },
  cardHeader: {flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 14},
  msIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardMeta: {flex: 1},
  cardTitle: {fontSize: 15, fontWeight: '700'},
  cardSubtitle: {fontSize: 13, marginTop: 2},
  statusDot: {width: 10, height: 10, borderRadius: 5},
  scopeRow: {flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 16},
  scopePill: {paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20},
  scopeText: {fontSize: 12, fontWeight: '600'},
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    borderRadius: 12,
  },
  btnDanger: {borderWidth: 1, backgroundColor: 'transparent'},
  btnText: {fontSize: 14, fontWeight: '700'},
  spinner: {marginVertical: 12},
  errorText: {fontSize: 12, marginTop: 10, textAlign: 'center'},
  infoBox: {
    flexDirection: 'row',
    gap: 10,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
  },
  infoText: {flex: 1, fontSize: 13, lineHeight: 18},
});
