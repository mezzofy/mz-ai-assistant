import {apiFetch} from './api';

export interface ModelUsage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  count: number;
}

export interface LlmUsageStats {
  total_messages: number;
  total_input_tokens: number;
  total_output_tokens: number;
  by_model: ModelUsage[];
  period: string;
}

export const getLlmUsageStats = (): Promise<LlmUsageStats> =>
  apiFetch<LlmUsageStats>('/llm/usage-stats');
