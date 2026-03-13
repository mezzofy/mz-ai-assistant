import React, {useState} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {forgotPasswordApi} from '../api/auth';

type Props = {
  navigation: any;
};

export const ForgotPasswordScreen: React.FC<Props> = ({navigation}) => {
  const colors = useTheme();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSendCode = async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      setError('Please enter your email address.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await forgotPasswordApi(trimmed);
      // Always navigate to OTP screen — backend always returns 200 (prevents enumeration)
      navigation.navigate('OTPVerification', {
        otp_token: '', // not used in forgot mode
        email: trimmed,
        mode: 'forgot',
      });
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={[styles.container, {backgroundColor: colors.primary}]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.inner}>
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
            <Icon name="key-outline" size={28} color={colors.accent} />
          </View>
          <Text style={[styles.title, {color: colors.text}]}>Forgot Password?</Text>
          <Text style={[styles.subtitle, {color: colors.textMuted}]}>
            Enter your email and we'll send you a verification code to reset your password.
          </Text>
        </View>

        {/* Email input */}
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="mail-outline" size={18} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={email}
            onChangeText={val => { setEmail(val); setError(null); }}
            placeholder="Email address"
            placeholderTextColor={colors.textDim}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
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
          onPress={handleSendCode}
          disabled={loading}
          activeOpacity={0.8}
          style={[
            styles.sendBtn,
            {backgroundColor: colors.accent, shadowColor: colors.accent},
            loading && {backgroundColor: colors.textDim, shadowOpacity: 0},
          ]}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.sendBtnText}>Send Code</Text>
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
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  inner: {flex: 1, paddingHorizontal: 32, paddingTop: 60},
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
    borderRadius: 14, borderWidth: 1, marginBottom: 16,
  },
  inputIcon: {paddingLeft: 16},
  input: {flex: 1, padding: 16, paddingLeft: 12, fontSize: 15},
  errorWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginBottom: 12, padding: 12, borderRadius: 10, borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 13, lineHeight: 18},
  sendBtn: {
    padding: 16, borderRadius: 14, alignItems: 'center',
    shadowOffset: {width: 0, height: 4}, shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  sendBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
  backLinkWrap: {marginTop: 20, alignItems: 'center'},
  backLinkText: {fontSize: 13},
});
