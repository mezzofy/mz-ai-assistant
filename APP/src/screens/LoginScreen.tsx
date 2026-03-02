import React, {useState} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useAuthStore} from '../stores/authStore';
import {useTheme} from '../hooks/useTheme';

export const LoginScreen: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const loginWithCredentials = useAuthStore(s => s.loginWithCredentials);
  const loading = useAuthStore(s => s.loading);
  const error = useAuthStore(s => s.error);
  const clearError = useAuthStore(s => s.clearError);
  const colors = useTheme();

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      return;
    }
    clearError();
    try {
      await loginWithCredentials(email.trim(), password);
      // Navigation automatic: App.tsx watches isLoggedIn; switches to MainTabs on true
    } catch {
      // Error displayed via authStore.error
    }
  };

  return (
    <KeyboardAvoidingView
      style={[styles.container, {backgroundColor: colors.primary}]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.inner}>
        <View style={styles.logoWrap}>
          <View style={[styles.logoCircle, {backgroundColor: colors.accent, shadowColor: colors.accent}]}>
            <Icon name="sparkles" size={36} color="#fff" />
          </View>
          <Text style={[styles.title, {color: colors.text}]}>Mezzofy AI</Text>
          <Text style={[styles.subtitle, {color: colors.textMuted}]}>Your intelligent work assistant</Text>
        </View>

        <View style={styles.form}>
          <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
            <Icon name="person-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="Email"
              placeholderTextColor={colors.textDim}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              style={[styles.input, {color: colors.text}]}
            />
          </View>
          <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
            <Icon name="lock-closed-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor={colors.textDim}
              secureTextEntry
              style={[styles.input, {color: colors.text}]}
            />
          </View>
        </View>

        {error ? (
          <View style={[styles.errorWrap, {backgroundColor: colors.danger + '18', borderColor: colors.danger + '33'}]}>
            <Icon name="alert-circle-outline" size={16} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          onPress={handleLogin}
          disabled={loading}
          activeOpacity={0.8}
          style={[
            styles.loginBtn,
            {backgroundColor: colors.accent, shadowColor: colors.accent},
            loading && {backgroundColor: colors.textDim, shadowOpacity: 0},
          ]}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.loginBtnText}>Sign In</Text>
          )}
        </TouchableOpacity>

        <Text style={[styles.forgot, {color: colors.textDim}]}>
          Forgot password? <Text style={{color: colors.accent}}>Reset here</Text>
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  inner: {flex: 1, justifyContent: 'center', paddingHorizontal: 32},
  logoWrap: {alignItems: 'center', marginBottom: 48},
  logoCircle: {
    width: 72, height: 72, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 20,
    shadowOffset: {width: 0, height: 8},
    shadowOpacity: 0.4, shadowRadius: 32, elevation: 12,
  },
  title: {fontSize: 26, fontWeight: '800', letterSpacing: -0.5},
  subtitle: {fontSize: 14, marginTop: 8},
  form: {gap: 14},
  inputWrap: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 14,
    borderWidth: 1, marginBottom: 14,
  },
  inputIcon: {paddingLeft: 16},
  input: {flex: 1, padding: 16, paddingLeft: 12, fontSize: 15},
  errorWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginTop: 4, marginBottom: 8, padding: 12, borderRadius: 10,
    borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 13, lineHeight: 18},
  loginBtn: {
    marginTop: 16, padding: 16, borderRadius: 14,
    alignItems: 'center',
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  loginBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
  forgot: {textAlign: 'center', fontSize: 13, marginTop: 20},
});
