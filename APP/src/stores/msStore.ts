import {create} from 'zustand';
import {getMsAuthStatusApi, deleteMsAuthDisconnectApi} from '../api/msOAuth';

type MsState = {
  connected: boolean;
  msEmail: string | null;
  scopes: string[];
  expiresAt: string | null;
  loading: boolean;
  error: string | null;
  loadStatus: () => Promise<void>;
  disconnect: () => Promise<void>;
  setConnected: (email: string, scopes: string[], expiresAt: string | null) => void;
  clearError: () => void;
};

export const useMsStore = create<MsState>(set => ({
  connected: false,
  msEmail: null,
  scopes: [],
  expiresAt: null,
  loading: false,
  error: null,

  loadStatus: async () => {
    set({loading: true, error: null});
    try {
      const status = await getMsAuthStatusApi();
      set({
        connected: status.connected,
        msEmail: status.ms_email,
        scopes: status.scopes,
        expiresAt: status.expires_at,
        loading: false,
      });
    } catch {
      set({loading: false});
    }
  },

  disconnect: async () => {
    set({loading: true, error: null});
    try {
      await deleteMsAuthDisconnectApi();
      set({connected: false, msEmail: null, scopes: [], expiresAt: null, loading: false});
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Disconnect failed. Please try again.';
      set({loading: false, error: message});
      throw e;
    }
  },

  setConnected: (email, scopes, expiresAt) => {
    set({connected: true, msEmail: email, scopes, expiresAt, error: null});
  },

  clearError: () => set({error: null}),
}));
