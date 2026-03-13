import AsyncStorage from '@react-native-async-storage/async-storage';
import {create} from 'zustand';
import {
  loginApi,
  logoutApi,
  getMeApi,
  verifyLoginOtpApi,
  resendLoginOtpApi,
  UserInfo,
  LoginResponse,
} from '../api/auth';
import {saveTokens, getAccessToken, getRefreshToken, clearTokens} from '../storage/tokenStorage';
import {registerUnauthorizedHandler} from '../api/api';
import {useChatStore} from './chatStore';

type AuthState = {
  isLoggedIn: boolean;
  user: UserInfo | null;
  accessToken: string | null;
  refreshToken: string | null;
  loading: boolean;
  error: string | null;
  // Two-phase login — holds OTP state between login and verify steps
  pendingOtpToken: string | null;
  pendingEmail: string | null;
  loginWithCredentials: (
    email: string,
    password: string,
  ) => Promise<{otp_token: string; email: string}>;
  verifyLoginOtp: (otp_token: string, code: string) => Promise<void>;
  resendLoginOtp: (otp_token: string) => Promise<void>;
  logout: () => Promise<void>;
  loadStoredUser: () => Promise<void>;
  clearError: () => void;
  login: () => void; // Legacy alias — keeps any remaining onPress={login} refs working
};

export const useAuthStore = create<AuthState>(set => {
  // Runs at module import time. Called by api.ts when both the original request
  // AND the token refresh fail with 401 — session definitively expired.
  registerUnauthorizedHandler(() => {
    // clearTokens() already called by api.ts before invoking this
    set({
      isLoggedIn: false,
      user: null,
      accessToken: null,
      refreshToken: null,
      pendingOtpToken: null,
      pendingEmail: null,
      error: 'Your session has expired. Please log in again.',
    });
  });

  return {
    isLoggedIn: false,
    user: null,
    accessToken: null,
    refreshToken: null,
    loading: false,
    error: null,
    pendingOtpToken: null,
    pendingEmail: null,

    loginWithCredentials: async (email, password) => {
      set({loading: true, error: null});
      try {
        const response = await loginApi(email.trim(), password);
        // Backend now returns otp_required — store pending state, do NOT set isLoggedIn
        set({
          pendingOtpToken: response.otp_token,
          pendingEmail: email.trim().toLowerCase(),
          loading: false,
          error: null,
        });
        return {otp_token: response.otp_token, email: email.trim()};
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : 'Login failed. Please try again.';
        set({loading: false, error: message});
        throw e;
      }
    },

    verifyLoginOtp: async (otp_token, code) => {
      set({loading: true, error: null});
      try {
        const response: LoginResponse = await verifyLoginOtpApi(otp_token, code);
        await saveTokens(response.access_token, response.refresh_token);
        set({
          isLoggedIn: true,
          user: response.user_info,
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          pendingOtpToken: null,
          pendingEmail: null,
          loading: false,
          error: null,
        });
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : 'Verification failed. Please try again.';
        set({loading: false, error: message});
        throw e;
      }
    },

    resendLoginOtp: async (otp_token) => {
      // Fire-and-forget — screen owns the countdown timer
      try {
        await resendLoginOtpApi(otp_token);
      } catch {
        // Swallowed — screen shows its own error if needed
      }
    },

    logout: async () => {
      const storedRefresh = await getRefreshToken();
      if (storedRefresh) {
        try {
          await logoutApi(storedRefresh); // Best-effort — proceed even if this fails
        } catch {
          // Swallowed — local logout proceeds regardless (access token will expire naturally)
        }
      }
      await clearTokens();
      // Clear in-memory chat so the next user starts with a clean slate
      useChatStore.getState().resetChat();
      // Clear persisted chat titles so this user's history is not visible to the next login
      await AsyncStorage.removeItem('@mz_chat_titles');
      set({
        isLoggedIn: false,
        user: null,
        accessToken: null,
        refreshToken: null,
        pendingOtpToken: null,
        pendingEmail: null,
        error: null,
      });
    },

    loadStoredUser: async () => {
      const storedAccess = await getAccessToken();
      if (!storedAccess) {
        return; // No stored session
      }
      try {
        // apiFetch auto-refreshes if the stored access token is expired
        const userInfo = await getMeApi();
        const freshAccess = await getAccessToken(); // re-read after possible silent refresh
        const storedRefresh = await getRefreshToken();
        set({
          isLoggedIn: true,
          user: userInfo,
          accessToken: freshAccess,
          refreshToken: storedRefresh,
        });
      } catch {
        // Both tokens failed — clear and stay logged out
        await clearTokens();
        set({isLoggedIn: false, user: null, accessToken: null, refreshToken: null});
      }
    },

    clearError: () => set({error: null}),

    login: () => set({isLoggedIn: true}), // Legacy alias
  };
});
