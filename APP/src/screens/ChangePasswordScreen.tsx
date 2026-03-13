import React, {useState, useEffect} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {changePasswordApi} from '../api/auth';

type Props = {
  navigation: any;
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

export const ChangePasswordScreen: React.FC<Props> = ({navigation}) => {
  const colors = useTheme();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const allRulesMet = PASSWORD_RULES.every(r => r.test(newPassword));
  const passwordsMatch = newPassword === confirmPassword && confirmPassword.length > 0;
  const canSubmit = currentPassword.length > 0 && allRulesMet && passwordsMatch;

  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => {
        navigation.goBack();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [successMessage, navigation]);

  const handleUpdate = async () => {
    if (!canSubmit) {return;}
    setError(null);
    setSuccessMessage(null);
    setLoading(true);
    try {
      await changePasswordApi(currentPassword, newPassword);
      setSuccessMessage('Password updated successfully!');
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
      {/* Header */}
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} activeOpacity={0.7} style={styles.backBtn}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.title, {color: colors.text}]}>Change Password</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.inner} keyboardShouldPersistTaps="handled">
        {/* Current password */}
        <Text style={[styles.label, {color: colors.textMuted}]}>Current Password</Text>
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="lock-closed-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={currentPassword}
            onChangeText={val => { setCurrentPassword(val); setError(null); }}
            placeholder="Enter current password"
            placeholderTextColor={colors.textDim}
            secureTextEntry={!showCurrent}
            style={[styles.input, {color: colors.text}]}
          />
          <TouchableOpacity onPress={() => setShowCurrent(v => !v)} style={styles.eyeBtn}>
            <Icon name={showCurrent ? 'eye-outline' : 'eye-off-outline'} size={18} color={colors.textDim} />
          </TouchableOpacity>
        </View>

        {/* New password */}
        <Text style={[styles.label, {color: colors.textMuted}]}>New Password</Text>
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="lock-open-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={newPassword}
            onChangeText={val => { setNewPassword(val); setError(null); }}
            placeholder="Enter new password"
            placeholderTextColor={colors.textDim}
            secureTextEntry={!showNew}
            style={[styles.input, {color: colors.text}]}
          />
          <TouchableOpacity onPress={() => setShowNew(v => !v)} style={styles.eyeBtn}>
            <Icon name={showNew ? 'eye-outline' : 'eye-off-outline'} size={18} color={colors.textDim} />
          </TouchableOpacity>
        </View>

        {/* Confirm new password */}
        <Text style={[styles.label, {color: colors.textMuted}]}>Confirm New Password</Text>
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="lock-open-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={confirmPassword}
            onChangeText={val => { setConfirmPassword(val); setError(null); }}
            placeholder="Confirm new password"
            placeholderTextColor={colors.textDim}
            secureTextEntry={!showConfirm}
            style={[styles.input, {color: colors.text}]}
          />
          <TouchableOpacity onPress={() => setShowConfirm(v => !v)} style={styles.eyeBtn}>
            <Icon name={showConfirm ? 'eye-outline' : 'eye-off-outline'} size={18} color={colors.textDim} />
          </TouchableOpacity>
        </View>

        {/* Password rules */}
        {newPassword.length > 0 && (
          <View style={[styles.rulesCard, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
            <Text style={[styles.rulesTitle, {color: colors.textMuted}]}>New password requirements</Text>
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
        )}

        {/* Error */}
        {error ? (
          <View style={[styles.errorWrap, {backgroundColor: colors.danger + '18', borderColor: colors.danger + '33'}]}>
            <Icon name="alert-circle-outline" size={16} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          </View>
        ) : null}

        {/* Success */}
        {successMessage ? (
          <View style={[styles.successWrap, {backgroundColor: '#22c55e18', borderColor: '#22c55e33'}]}>
            <Icon name="checkmark-circle-outline" size={16} color="#22c55e" />
            <Text style={[styles.errorText, {color: '#22c55e'}]}>{successMessage}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          onPress={handleUpdate}
          disabled={loading || !canSubmit}
          activeOpacity={0.8}
          style={[
            styles.updateBtn,
            {backgroundColor: colors.accent, shadowColor: colors.accent},
            (loading || !canSubmit) && {backgroundColor: colors.textDim, shadowOpacity: 0},
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
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {width: 36, height: 36, alignItems: 'center', justifyContent: 'center'},
  title: {fontSize: 17, fontWeight: '700'},
  inner: {paddingHorizontal: 24, paddingTop: 24, paddingBottom: 40},
  label: {fontSize: 12, fontWeight: '600', letterSpacing: 0.5, marginBottom: 8, marginLeft: 4},
  inputWrap: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 14, borderWidth: 1, marginBottom: 20,
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
  successWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginBottom: 12, padding: 12, borderRadius: 10, borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 13, lineHeight: 18},
  updateBtn: {
    padding: 16, borderRadius: 14, alignItems: 'center',
    shadowOffset: {width: 0, height: 4}, shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
    marginTop: 8,
  },
  updateBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
});
