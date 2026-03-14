import {create} from 'zustand';
import {listScheduledJobsApi, ScheduledJob} from '../api/schedulerApi';

type SchedulerState = {
  jobs: ScheduledJob[];
  loading: boolean;
  error: string | null;
  loadJobs: () => Promise<void>;
};

export const useSchedulerStore = create<SchedulerState>((set) => ({
  jobs: [],
  loading: false,
  error: null,

  loadJobs: async () => {
    set({loading: true, error: null});
    try {
      const result = await listScheduledJobsApi();
      set({jobs: result.jobs, loading: false});
    } catch (e: any) {
      set({loading: false, error: e?.message ?? 'Failed to load scheduled tasks'});
    }
  },
}));
