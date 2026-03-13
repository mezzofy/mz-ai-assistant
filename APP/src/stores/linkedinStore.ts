import {create} from 'zustand';
import {getLinkedInStatusApi} from '../api/linkedinApi';

type LinkedInState = {
  configured: boolean;
  sessionPreview: string | null;
  rateLimit: number;
  sessionUses: number;
  loading: boolean;
  error: string | null;
  loadStatus: () => Promise<void>;
};

export const useLinkedInStore = create<LinkedInState>(set => ({
  configured: false,
  sessionPreview: null,
  rateLimit: 50,
  sessionUses: 0,
  loading: false,
  error: null,

  loadStatus: async () => {
    set({loading: true, error: null});
    try {
      const status = await getLinkedInStatusApi();
      set({
        configured: status.configured,
        sessionPreview: status.session_preview,
        rateLimit: status.rate_limit,
        sessionUses: status.session_uses,
        loading: false,
      });
    } catch {
      set({loading: false});
    }
  },
}));
