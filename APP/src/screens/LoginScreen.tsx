import React, {useState} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {BRAND} from '../utils/theme';
import {useAuthStore} from '../stores/authStore';

export const LoginScreen: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const loginWithCredentials = useAuthStore(s => s.loginWithCredentials);
  const loading = useAuthStore(s => s.loading);
  const error = useAuthStore(s => s.error);
  const clearError = useAuthStore(s => s.clearError);

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
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.inner}>
        <View style={styles.logoWrap}>
          <View style={styles.logoCircle}>
            <Icon name="sparkles" size={36} color="#fff" />
          </View>
          <Text style={styles.title}>Mezzofy AI</Text>
          <Text style={styles.subtitle}>Your intelligent work assistant</Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputWrap}>
            <Icon name="person-outline" size={18} color={BRAND.textDim} style={styles.inputIcon} />
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="Email"
              placeholderTextColor={BRAND.textDim}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              style={styles.input}
            />
          </View>
          <View style={styles.inputWrap}>
            <Icon name="lock-closed-outline" size={18} color={BRAND.textDim} style={styles.inputIcon} />
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor={BRAND.textDim}
              secureTextEntry
              style={styles.input}
            />
          </View>
        </View>

        {error ? (
          <View style={styles.errorWrap}>
            <Icon name="alert-circle-outline" size={16} color={BRAND.danger} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          onPress={handleLogin}
          disabled={loading}
          activeOpacity={0.8}
          style={[styles.loginBtn, loading && styles.loginBtnDisabled]}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.loginBtnText}>Sign In</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.forgot}>
          Forgot password? <Text style={styles.forgotLink}>Reset here</Text>
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: BRAND.primary},
  inner: {flex: 1, justifyContent: 'center', paddingHorizontal: 32},
  logoWrap: {alignItems: 'center', marginBottom: 48},
  logoCircle: {
    width: 72, height: 72, borderRadius: 20,
    backgroundColor: BRAND.accent, alignItems: 'center', justifyContent: 'center',
    marginBottom: 20,
    shadowColor: BRAND.accent, shadowOffset: {width: 0, height: 8},
    shadowOpacity: 0.4, shadowRadius: 32, elevation: 12,
  },
  title: {color: BRAND.text, fontSize: 26, fontWeight: '800', letterSpacing: -0.5},
  subtitle: {color: BRAND.textMuted, fontSize: 14, marginTop: 8},
  form: {gap: 14},
  inputWrap: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: BRAND.surfaceLight, borderRadius: 14,
    borderWidth: 1, borderColor: BRAND.border, marginBottom: 14,
  },
  inputIcon: {paddingLeft: 16},
  input: {flex: 1, padding: 16, paddingLeft: 12, color: BRAND.text, fontSize: 15},
  errorWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginTop: 4, marginBottom: 8, padding: 12, borderRadius: 10,
    backgroundColor: BRAND.danger + '18',
    borderWidth: 1, borderColor: BRAND.danger + '33',
  },
  errorText: {flex: 1, color: BRAND.danger, fontSize: 13, lineHeight: 18},
  loginBtn: {
    marginTop: 16, padding: 16, borderRadius: 14,
    backgroundColor: BRAND.accent, alignItems: 'center',
    shadowColor: BRAND.accent, shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  loginBtnDisabled: {backgroundColor: BRAND.textDim, shadowOpacity: 0},
  loginBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
  forgot: {textAlign: 'center', color: BRAND.textDim, fontSize: 13, marginTop: 20},
  forgotLink: {color: BRAND.accent},
});
