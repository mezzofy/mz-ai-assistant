import {apiFetch} from './api';

// ── Response types ────────────────────────────────────────────────────────────

export interface ChatArtifact {
  id: string | null;
  type: string;
  name: string;
  download_url: string | null;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  input_processed: {summary: string} | null;
  artifacts: ChatArtifact[];
  agent_used: string;
  tools_used: string[];
  success: boolean;
}

export interface SessionSummary {
  session_id: string;
  message_count: number;
  last_message: {role: string; content: string; timestamp: string} | null;
  created_at: string;
  updated_at: string;
}

export interface SessionsResponse {
  sessions: SessionSummary[];
  total: number;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface HistoryResponse {
  session_id: string;
  messages: HistoryMessage[];
}

// ── API functions ─────────────────────────────────────────────────────────────

export const sendTextApi = (
  message: string,
  sessionId?: string | null,
): Promise<ChatResponse> =>
  apiFetch<ChatResponse>('/chat/send', {
    method: 'POST',
    body: JSON.stringify({
      message,
      ...(sessionId ? {session_id: sessionId} : {}),
    }),
  });

export const sendUrlApi = (
  url: string,
  message?: string | null,
  sessionId?: string | null,
): Promise<ChatResponse> =>
  apiFetch<ChatResponse>('/chat/send-url', {
    method: 'POST',
    body: JSON.stringify({
      url,
      ...(message ? {message} : {}),
      ...(sessionId ? {session_id: sessionId} : {}),
    }),
  });

// Used when a real file URI is available (8C+). In 8B, media modes fall back to sendTextApi.
export const sendMediaApi = (
  fileUri: string,
  fileName: string,
  mimeType: string,
  inputType: 'image' | 'video' | 'audio' | 'file',
  message?: string | null,
  sessionId?: string | null,
): Promise<ChatResponse> => {
  const form = new FormData();
  // React Native FormData file: pass object with uri/name/type
  form.append('media_file', {uri: fileUri, name: fileName, type: mimeType} as unknown as Blob);
  form.append('input_type', inputType);
  if (message) {
    form.append('message', message);
  }
  if (sessionId) {
    form.append('session_id', sessionId);
  }
  return apiFetch<ChatResponse>('/chat/send-media', {
    method: 'POST',
    body: form,
  });
};

export const getSessionsApi = (): Promise<SessionsResponse> =>
  apiFetch<SessionsResponse>('/chat/sessions');

export const getHistoryApi = (sessionId: string): Promise<HistoryResponse> =>
  apiFetch<HistoryResponse>(`/chat/history/${sessionId}`);
