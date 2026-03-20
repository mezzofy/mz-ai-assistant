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
  task_id?: string | null;
  status?: string;  // 'queued' for 202 background tasks; absent for sync responses
}

export interface SessionSummary {
  session_id: string;
  message_count: number;
  last_message: {role: string; content: string; timestamp: string} | null;
  created_at: string;
  updated_at: string;
  is_favorite: boolean;
  is_archived: boolean;
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

export interface SessionPatchRequest {
  is_favorite?: boolean;
  is_archived?: boolean;
}

export const patchSessionApi = (
  sessionId: string,
  patch: SessionPatchRequest,
): Promise<{success: boolean}> =>
  apiFetch<{success: boolean}>(`/chat/session/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });

export const sendArtifactApi = (
  artifactId: string,
  message: string,
  sessionId?: string | null,
): Promise<ChatResponse> =>
  apiFetch<ChatResponse>('/chat/send-artifact', {
    method: 'POST',
    body: JSON.stringify({
      artifact_id: artifactId,
      message,
      ...(sessionId ? {session_id: sessionId} : {}),
    }),
  });

export interface TaskSummary {
  id: string;
  session_id: string | null;
  title: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  queue_name: string;
  created_at: string;
  progress?: number;            // 0–100; updated by _update_agent_task_step()
  current_step?: string | null; // JSON string: {agent, tool, iteration, description, ...}
  started_at?: string | null;   // ISO timestamp
  result?: { response?: string; artifacts?: any[] } | null;
}

export interface TasksResponse {
  tasks: TaskSummary[];
  total: number;
}

export const getTasksApi = (): Promise<TasksResponse> =>
  apiFetch<TasksResponse>('/tasks/');

export const getActiveTasksApi = (): Promise<TasksResponse> =>
  apiFetch<TasksResponse>('/tasks/active');

export const getTaskByIdApi = (taskId: string): Promise<any> =>
  apiFetch<any>(`/tasks/${taskId}`);
