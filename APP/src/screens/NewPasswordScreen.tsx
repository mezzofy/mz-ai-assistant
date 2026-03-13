import React, {useState} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, Alert,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {resetPasswordApi} from '../api/auth';

type Props = {
  navigation: any;
  route: {params: {reset_token: string}};
};

interface Rule {
  label: string;
  test: (p: string) => boolean;
}

const PASSWORD_RULES: Rule[] = [
  {label: 'At least 8 characters', test: p => p.length >= 8},
  {label: 'Uppercase letter (A-Z)', test: p => /[A-Z]/.test(p)},
  {label: 'Lowercase letter (a-z)', test: p => /[a-z]/.test(p)},
  {label: 'Number (0-9)', test: p => /\d/.test(p)},
  {label: 'Special character (!@#$...)', test: p => /[!@#$%^&*()_+\-=\[\]{}|;:'",.<>?`~\\]/.test(p)},
];

export const NewPasswordScreen: React.FC<Props> = ({navigation, route}) => {
  const {reset_token} = route.params;
  const colors = useTheme();

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allRulesMet = PASSWORD_RULES.every(r => r.test(newPassword));
  const passwordsMatch = newPassword === confirmPassword;

  const handleUpdate = async () => {
    if (!allRulesMet) {
      setError('Please meet all password requirements.');
      return;
    }
    if (!passwordsMatch) {
      setError('Passwords do not match.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await resetPasswordApi(reset_token, newPassword);
      Alert.alert(
        'Password Updated',
        'Your password has been changed successfully.',
        [{text: 'Sign In', onPress: () => navigation.navigate('Login')}],
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to update password.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={[styles.container, {backgroundColor: colors.primary}]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.inner} keyboardShouldPersistTaps="handled">
        {/* Back button */}
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={styles.backBtn}
          activeOpacity={0.7}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>

        {/* Header */}
        <View style={styles.headerWrap}>
          <View style={[styles.iconCircle, {backgroundColor: colors.accentSoft}]}>
            <Icon name="lock-closed-outline" size={28} color={colors.accent} />
          </View>
          <Text style={[styles.title, {color: colors.text}]}>Set New Password</Text>
          <Text style={[styles.subtitle, {color: colors.textMuted}]}>
            Choose a strong password for your account.
          </Text>
        </View>

        {/* New password */}
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="lock-closed-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={newPassword}
            onChangeText={val => { setNewPassword(val); setError(null); }}
            placeholder="New password"
            placeholderTextColor={colors.textDim}
            secureTextEntry={!showNew}
            style={[styles.input, {color: colors.text}]}
          />
          <TouchableOpacity onPress={() => setShowNew(v => !v)} style={styles.eyeBtn}>
            <Icon name={showNew ? 'eye-outline' : 'eye-off-outline'} size={18} color={colors.textDim} />
          </TouchableOpacity>
        </View>

        {/* Confirm password */}
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="lock-closed-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={confirmPassword}
            onChangeText={val => { setConfirmPassword(val); setError(null); }}
            placeholder="Confirm password"
            placeholderTextColor={colors.textDim}
            secureTextEntry={!showConfirm}
            style={[styles.input, {color: colors.text}]}
          />
          <TouchableOpacity onPress={() => setShowConfirm(v => !v)} style={styles.eyeBtn}>
            <Icon name={showConfirm ? 'eye-outline' : 'eye-off-outline'} size={18} color={colors.textDim} />
          </TouchableOpacity>
        </View>

        {/* Password rules */}
        <View style={[styles.rulesCard, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Text style={[styles.rulesTitle, {color: colors.textMuted}]}>Password requirements</Text>
          {PASSWORD_RULES.map(rule => {
            const met = rule.test(newPassword);
            return (
              <View key={rule.label} style={styles.ruleRow}>
                <Icon
                  name={met ? 'checkmark-circle' : 'ellipse-outline'}
                  size={16}
                  color={met ? '#22c55e' : colors.textDim}
                />
                <Text style={[styles.ruleText, {color: met ? colors.text : colors.textDim}]}>
                  {rule.label}
                </Text>
              </View>
            );
          })}
          {confirmPassword.length > 0 && (
            <View style={styles.ruleRow}>
              <Icon
                name={passwordsMatch ? 'checkmark-circle' : 'close-circle'}
                size={16}
                color={passwordsMatch ? '#22c55e' : colors.danger}
              />
              <Text style={[styles.ruleText, {color: passwordsMatch ? colors.text : colors.danger}]}>
                Passwords match
              </Text>
            </View>
          )}
        </View>

        {error ? (
          <View style={[styles.errorWrap, {backgroundColor: colors.danger + '18', borderColor: colors.danger + '33'}]}>
            <Icon name="alert-circle-outline" size={16} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          onPress={handleUpdate}
          disabled={loading || !allRulesMet || !passwordsMatch}
          activeOpacity={0.8}
          style={[
            styles.updateBtn,
            {backgroundColor: colors.accent, shadowColor: colors.accent},
            (loading || !allRulesMet || !passwordsMatch) && {backgroundColor: colors.textDim, shadowOpacity: 0},
          ]}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.updateBtnText}>Update Password</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  inner: {paddingHorizontal: 32, paddingTop: 60, paddingBottom: 40},
  backBtn: {marginBottom: 32},
  headerWrap: {alignItems: 'center', marginBottom: 32},
  iconCircle: {
    width: 72, height: 72, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center', marginBottom: 20,
  },
  title: {fontSize: 24, fontWeight: '800', marginBottom: 10, letterSpacing: -0.5},
  subtitle: {fontSize: 14, textAlign: 'center', lineHeight: 22},
  inputWrap: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 14, borderWidth: 1, marginBottom: 12,
  },
  inputIcon: {paddingLeft: 16},
  input: {flex: 1, padding: 16, paddingLeft: 12, fontSize: 15},
  eyeBtn: {padding: 16},
  rulesCard: {
    borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 16, gap: 10,
  },
  rulesTitle: {fontSize: 12, fontWeight: '600', letterSpacing: 0.5, marginBottom: 4},
  ruleRow: {flexDirection: 'row', alignItems: 'center', gap: 10},
  ruleText: {fontSize: 13},
  errorWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginBottom: 12, padding: 12, borderRadius: 10, borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 13, lineHeight: 18},
  updateBtn: {
    padding: 16, borderRadius: 14, alignItems: 'center',
    shadowOffset: {width: 0, height: 4}, shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  updateBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
});
