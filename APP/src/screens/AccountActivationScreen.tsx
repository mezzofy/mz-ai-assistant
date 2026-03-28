import React, {useState} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {activateAccountApi} from '../api/auth';

type Props = {
  navigation: any;
};

export const AccountActivationScreen: React.FC<Props> = ({navigation}) => {
  const colors = useTheme();
  const [inviteToken, setInviteToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleActivate = async () => {
    const token = inviteToken.trim();
    if (!token) {
      setError('Please enter your activation code.');
      return;
    }
    if (!newPassword) {
      setError('Please enter a new password.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setError(null);
    setLoading(true);
    try {
      await activateAccountApi(token, newPassword);
      setSuccess(true);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Activation failed. Please check your code and try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <View style={[styles.container, {backgroundColor: colors.primary}]}>
        <View style={styles.successWrap}>
          <View style={[styles.iconCircle, {backgroundColor: colors.accentSoft}]}>
            <Icon name="checkmark-circle" size={40} color={colors.accent} />
          </View>
          <Text style={[styles.successTitle, {color: colors.text}]}>Account Activated!</Text>
          <Text style={[styles.successSub, {color: colors.textMuted}]}>
            Your account is now active. Sign in with your email and new password.
          </Text>
          <TouchableOpacity
            onPress={() => navigation.navigate('Login')}
            activeOpacity={0.8}
            style={[styles.signInBtn, {backgroundColor: colors.accent, shadowColor: colors.accent}]}>
            <Text style={styles.signInBtnText}>Sign In</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={[styles.container, {backgroundColor: colors.primary}]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        contentContainerStyle={styles.inner}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={styles.backBtn}
          activeOpacity={0.7}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>

        <View style={styles.headerWrap}>
          <View style={[styles.iconCircle, {backgroundColor: colors.accentSoft}]}>
            <Icon name="shield-checkmark-outline" size={28} color={colors.accent} />
          </View>
          <Text style={[styles.title, {color: colors.text}]}>Activate Account</Text>
          <Text style={[styles.subtitle, {color: colors.textMuted}]}>
            Enter the activation code from your invite email and set a new password.
          </Text>
        </View>

        {/* Invite token */}
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="key-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={inviteToken}
            onChangeText={val => { setInviteToken(val); setError(null); }}
            placeholder="Activation code"
            placeholderTextColor={colors.textDim}
            autoCapitalize="none"
            autoCorrect={false}
            style={[styles.input, {color: colors.text}]}
          />
        </View>

        {/* New password */}
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="lock-closed-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={newPassword}
            onChangeText={val => { setNewPassword(val); setError(null); }}
            placeholder="New password"
            placeholderTextColor={colors.textDim}
            secureTextEntry
            style={[styles.input, {color: colors.text}]}
          />
        </View>

        {/* Confirm password */}
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="lock-closed-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={confirmPassword}
            onChangeText={val => { setConfirmPassword(val); setError(null); }}
            placeholder="Confirm password"
            placeholderTextColor={colors.textDim}
            secureTextEntry
            style={[styles.input, {color: colors.text}]}
          />
        </View>

        {error ? (
          <View style={[styles.errorWrap, {backgroundColor: colors.danger + '18', borderColor: colors.danger + '33'}]}>
            <Icon name="alert-circle-outline" size={16} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          onPress={handleActivate}
          disabled={loading}
          activeOpacity={0.8}
          style={[
            styles.activateBtn,
            {backgroundColor: colors.accent, shadowColor: colors.accent},
            loading && {backgroundColor: colors.textDim, shadowOpacity: 0},
          ]}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.activateBtnText}>Activate Account</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={styles.backLinkWrap}
          activeOpacity={0.7}>
          <Text style={[styles.backLinkText, {color: colors.textDim}]}>
            {'Back to '}
            <Text style={{color: colors.accent, fontWeight: '600'}}>Sign In</Text>
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  inner: {paddingHorizontal: 32, paddingTop: 60, paddingBottom: 40},
  backBtn: {marginBottom: 32},
  headerWrap: {alignItems: 'center', marginBottom: 40},
  iconCircle: {
    width: 72, height: 72, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center', marginBottom: 20,
  },
  title: {fontSize: 24, fontWeight: '800', marginBottom: 10, letterSpacing: -0.5},
  subtitle: {fontSize: 14, textAlign: 'center', lineHeight: 22},
  inputWrap: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 14, borderWidth: 1, marginBottom: 14,
  },
  inputIcon: {paddingLeft: 16},
  input: {flex: 1, padding: 16, paddingLeft: 12, fontSize: 15},
  errorWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginBottom: 12, padding: 12, borderRadius: 10, borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 13, lineHeight: 18},
  activateBtn: {
    padding: 16, borderRadius: 14, alignItems: 'center',
    shadowOffset: {width: 0, height: 4}, shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  activateBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
  backLinkWrap: {marginTop: 20, alignItems: 'center'},
  backLinkText: {fontSize: 13},
  // Success state
  successWrap: {flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 32},
  successTitle: {fontSize: 24, fontWeight: '800', marginBottom: 12, letterSpacing: -0.5},
  successSub: {fontSize: 14, textAlign: 'center', lineHeight: 22, marginBottom: 40},
  signInBtn: {
    width: '100%', padding: 16, borderRadius: 14, alignItems: 'center',
    shadowOffset: {width: 0, height: 4}, shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  signInBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
});
