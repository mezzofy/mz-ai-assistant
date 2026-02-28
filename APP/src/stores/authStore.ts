import {create} from 'zustand';
import {loginApi, logoutApi, getMeApi, UserInfo} from '../api/auth';
import {saveTokens, getAccessToken, getRefreshToken, clearTokens} from '../storage/tokenStorage';
import {registerUnauthorizedHandler} from '../api/api';

type AuthState = {
  isLoggedIn: boolean;
  user: UserInfo | null;
  accessToken: string | null;
  refreshToken: string | null;
  loading: boolean;
  error: string | null;
  loginWithCredentials: (email: string, password: string) => Promise<void>;
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

    loginWithCredentials: async (email, password) => {
      set({loading: true, error: null});
      try {
        const response = await loginApi(email.trim(), password);
        await saveTokens(response.access_token, response.refresh_token);
        // user_info from login already has id, name, department, role, permissions
        // No extra /auth/me call needed — avoids an extra round trip
        set({
          isLoggedIn: true,
          user: response.user_info,
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          loading: false,
          error: null,
        });
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : 'Login failed. Please try again.';
        set({loading: false, error: message});
        throw e;
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
      set({isLoggedIn: false, user: null, accessToken: null, refreshToken: null, error: null});
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
