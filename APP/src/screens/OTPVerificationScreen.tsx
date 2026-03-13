import React, {useState, useEffect, useRef} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform, Alert,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useAuthStore} from '../stores/authStore';
import {useTheme} from '../hooks/useTheme';
import {verifyResetOtpApi, resendLoginOtpApi} from '../api/auth';

type Props = {
  navigation: any;
  route: {
    params: {
      otp_token: string;
      email: string;
      mode: 'login' | 'forgot';
    };
  };
};

const OTP_LENGTH = 6;
const RESEND_COOLDOWN = 60;
const OTP_EXPIRY_SECONDS = 300;

export const OTPVerificationScreen: React.FC<Props> = ({navigation, route}) => {
  const {otp_token, email, mode} = route.params;
  const colors = useTheme();

  const verifyLoginOtp = useAuthStore(s => s.verifyLoginOtp);
  const loading = useAuthStore(s => s.loading);
  const clearError = useAuthStore(s => s.clearError);

  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [error, setError] = useState<string | null>(null);
  const [resendCountdown, setResendCountdown] = useState(RESEND_COOLDOWN);
  const [expiryCountdown, setExpiryCountdown] = useState(OTP_EXPIRY_SECONDS);
  const [verifying, setVerifying] = useState(false);

  const inputRefs = useRef<(TextInput | null)[]>([]);

  // Resend cooldown timer
  useEffect(() => {
    if (resendCountdown <= 0) {return;}
    const timer = setInterval(() => {
      setResendCountdown(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCountdown]);

  // OTP expiry countdown (display only)
  useEffect(() => {
    if (expiryCountdown <= 0) {return;}
    const timer = setInterval(() => {
      setExpiryCountdown(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [expiryCountdown]);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleDigitChange = (value: string, index: number) => {
    const cleaned = value.replace(/[^0-9]/g, '').slice(-1);
    const next = [...digits];
    next[index] = cleaned;
    setDigits(next);
    setError(null);

    if (cleaned && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
    if (cleaned && index === OTP_LENGTH - 1) {
      // Auto-submit when last digit entered
      handleVerify(next.join(''));
    }
  };

  const handleKeyPress = (e: any, index: number) => {
    if (e.nativeEvent.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleVerify = async (codeOverride?: string) => {
    const code = codeOverride ?? digits.join('');
    if (code.length < OTP_LENGTH) {
      setError('Please enter all 6 digits.');
      return;
    }
    setError(null);
    setVerifying(true);

    try {
      if (mode === 'login') {
        await verifyLoginOtp(otp_token, code);
        // On success App.tsx switches to MainTabs automatically (isLoggedIn → true)
      } else {
        // forgot mode
        const result = await verifyResetOtpApi(email, code);
        navigation.navigate('NewPassword', {reset_token: result.reset_token});
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Verification failed.';
      setError(msg);
      // Clear digits on error
      setDigits(Array(OTP_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } finally {
      setVerifying(false);
    }
  };

  const handleResend = async () => {
    if (resendCountdown > 0) {return;}
    try {
      if (mode === 'login') {
        await resendLoginOtpApi(otp_token);
      }
      // For forgot mode the screen navigated from ForgotPassword — resend is not wired here
      setResendCountdown(RESEND_COOLDOWN);
      setExpiryCountdown(OTP_EXPIRY_SECONDS);
      setDigits(Array(OTP_LENGTH).fill(''));
      setError(null);
      inputRefs.current[0]?.focus();
    } catch {
      setError('Failed to resend code. Please try again.');
    }
  };

  const isLoading = loading || verifying;

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
            <Icon name="mail-outline" size={28} color={colors.accent} />
          </View>
          <Text style={[styles.title, {color: colors.text}]}>Verify Your Identity</Text>
          <Text style={[styles.subtitle, {color: colors.textMuted}]}>
            Enter the 6-digit code sent to{'\n'}
            <Text style={{color: colors.text, fontWeight: '600'}}>{email}</Text>
          </Text>
        </View>

        {/* OTP digit inputs */}
        <View style={styles.otpRow}>
          {digits.map((digit, i) => (
            <TextInput
              key={i}
              ref={ref => { inputRefs.current[i] = ref; }}
              value={digit}
              onChangeText={val => handleDigitChange(val, i)}
              onKeyPress={e => handleKeyPress(e, i)}
              keyboardType="number-pad"
              maxLength={1}
              selectTextOnFocus
              style={[
                styles.otpBox,
                {
                  backgroundColor: colors.surfaceLight,
                  borderColor: digit ? colors.accent : colors.border,
                  color: colors.text,
                },
                error && styles.otpBoxError,
              ]}
            />
          ))}
        </View>

        {/* Error */}
        {error ? (
          <View style={[styles.errorWrap, {backgroundColor: colors.danger + '18', borderColor: colors.danger + '33'}]}>
            <Icon name="alert-circle-outline" size={16} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          </View>
        ) : null}

        {/* Expiry countdown */}
        <Text style={[styles.expiryText, {color: expiryCountdown < 60 ? colors.danger : colors.textDim}]}>
          Code expires in {formatTime(expiryCountdown)}
        </Text>

        {/* Verify button */}
        <TouchableOpacity
          onPress={() => handleVerify()}
          disabled={isLoading || digits.join('').length < OTP_LENGTH}
          activeOpacity={0.8}
          style={[
            styles.verifyBtn,
            {backgroundColor: colors.accent, shadowColor: colors.accent},
            (isLoading || digits.join('').length < OTP_LENGTH) && {backgroundColor: colors.textDim, shadowOpacity: 0},
          ]}>
          {isLoading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.verifyBtnText}>Verify Code</Text>
          )}
        </TouchableOpacity>

        {/* Resend */}
        <TouchableOpacity
          onPress={handleResend}
          disabled={resendCountdown > 0}
          activeOpacity={0.7}
          style={styles.resendWrap}>
          <Text style={[styles.resendText, {color: colors.textDim}]}>
            {"Didn't receive a code? "}
            <Text style={{color: resendCountdown > 0 ? colors.textDim : colors.accent, fontWeight: '600'}}>
              {resendCountdown > 0 ? `Resend in ${resendCountdown}s` : 'Resend Code'}
            </Text>
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
  otpRow: {flexDirection: 'row', justifyContent: 'center', gap: 10, marginBottom: 16},
  otpBox: {
    width: 48, height: 56, borderRadius: 12, borderWidth: 2,
    textAlign: 'center', fontSize: 22, fontWeight: '700',
  },
  otpBoxError: {borderColor: '#FF4B6E'},
  errorWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginBottom: 12, padding: 12, borderRadius: 10, borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 13, lineHeight: 18},
  expiryText: {textAlign: 'center', fontSize: 13, marginBottom: 24},
  verifyBtn: {
    padding: 16, borderRadius: 14, alignItems: 'center',
    shadowOffset: {width: 0, height: 4}, shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  verifyBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
  resendWrap: {marginTop: 20, alignItems: 'center'},
  resendText: {fontSize: 13, textAlign: 'center'},
});
