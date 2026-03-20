import {create} from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  sendTextApi,
  sendUrlApi,
  sendMediaApi,
  sendArtifactApi,
  getSessionsApi,
  getHistoryApi,
  getTasksApi,
  getActiveTasksApi,
  getTaskByIdApi,
  patchSessionApi,
  ChatResponse,
  SessionSummary,
  TaskSummary,
} from '../api/chat';
import {mzWs} from '../api/websocket';

export type MediaInfo = {
  type: string;
  name: string;
  size: string;
  emoji: string;
  mimeType?: string;
};

// Matches server artifact shape from processor.py process_result()
export type Artifact = {
  id: string | null;
  type: string;
  name: string;
  download_url: string | null;
};

export type Message = {
  id: number;
  role: 'user' | 'assistant' | 'system';
  text: string;
  time: string;
  type?: string;
  media?: MediaInfo;
  artifacts?: Artifact[];
  tools?: string[];
  agentUsed?: string;   // e.g. "legal", "management", "finance"
  isSystem?: boolean;   // true for handoff divider messages
};

export const DEPT_TO_PERSONA: Record<string, string> = {
  management: 'Max',
  finance: 'Fiona',
  sales: 'Sam',
  marketing: 'Maya',
  support: 'Suki',
  hr: 'Hana',
  legal: 'Leo',
  research: 'Rex',
  developer: 'Dev',
  scheduler: 'Sched',
};

export type SelectedArtifact = {
  id: string;
  filename: string;
  file_type: string;
};

type ChatState = {
  messages: Message[];
  sessionId: string | null;
  isTyping: boolean;
  error: string | null;
  statusMessage: string | null;
  inputMode: string;
  showModes: boolean;
  recording: boolean;
  recordTime: number;
  mediaPreview: MediaInfo | null;
  selectedArtifact: SelectedArtifact | null;
  sessions: SessionSummary[];
  tasks: TaskSummary[];
  activeTask: TaskSummary | null;
  sessionTitles: Record<string, string>;
  // Primitive setters (used by ChatScreen UI)
  addMessage: (msg: Message) => void;
  setIsTyping: (v: boolean) => void;
  setInputMode: (v: string) => void;
  setShowModes: (v: boolean) => void;
  setRecording: (v: boolean) => void;
  setRecordTime: (v: number) => void;
  setMediaPreview: (v: MediaInfo | null) => void;
  setSelectedArtifact: (v: SelectedArtifact | null) => void;
  setSessionId: (id: string | null) => void;
  clearError: () => void;
  clearActiveTask: () => void;
  // Session title management
  loadTitles: () => Promise<void>;
  setSessionTitle: (sessionId: string, title: string) => Promise<void>;
  // API actions
  sendToServer: (text: string, mode: string, media: MediaInfo | null, mediaUri?: string | null) => Promise<void>;
  sendArtifactToServer: (artifactId: string, message: string) => Promise<void>;
  loadSessions: () => Promise<void>;
  loadTasks: () => Promise<void>;
  pollActiveTask: (sessionId: string) => Promise<void>;
  loadHistory: (sessionId: string) => Promise<void>;
  resetChat: () => void;
  toggleFavorite: (sessionId: string) => Promise<void>;
  toggleArchive: (sessionId: string) => Promise<void>;
};

const getTimeStr = () =>
  new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});

const PERSONA_GREETINGS: Record<string, string> = {
  management: "Hi, I'm Max, your AI management orchestrator. I coordinate across all departments, aggregate KPIs, and keep operations running smoothly.",
  finance:    "Hi, I'm Fiona, your AI finance analyst. I handle P&L reports, budget tracking, cash flow analysis, and financial forecasting.",
  sales:      "Hi, I'm Sam, your AI sales partner. I track pipelines, rep performance, customer acquisition metrics, and revenue targets.",
  marketing:  "Hi, I'm Maya, your AI marketing strategist. I manage campaign analytics, brand insights, and customer engagement reports.",
  support:    "Hi, I'm Suki, your AI customer support specialist. I analyse tickets, draft responses, and surface support trends.",
  hr:         "Hi, I'm Hana, your AI HR specialist. I help with onboarding workflows, people analytics, and HR policy guidance.",
  legal:      "Hi, I'm Leo, your AI legal counsel. I review contracts, advise on compliance, and cover jurisdictions across Singapore, HK, Malaysia, and the GCC.",
  research:   "Hi, I'm Rex, your AI research agent. I perform deep web research, competitive analysis, and market intelligence on any topic.",
  developer:  "Hi, I'm Dev, your AI developer agent. I assist with code generation, debugging, architecture decisions, and technical documentation.",
  scheduler:  "Hi, I'm Sched, your AI scheduling agent. I manage automated jobs, task pipelines, and system workflows.",
};

const GENERIC_GREETING = "Hi, I'm your Mezzofy AI assistant, here to help your team work smarter.";

const buildWelcomeMsg = (): Message => {
  // Determine time-of-day greeting using HKT (UTC+8)
  const nowUtcMs = Date.now();
  const hktOffsetMs = 8 * 60 * 60 * 1000;
  const hktHour = new Date(nowUtcMs + hktOffsetMs).getUTCHours();
  const timeGreeting =
    hktHour < 12 ? 'Good morning'
    : hktHour < 18 ? 'Good afternoon'
    : 'Good evening';

  // Get department from auth store (lazy import avoids circular dependency)
  const {useAuthStore} = require('./authStore');
  const dept: string | undefined = useAuthStore.getState().user?.department?.toLowerCase();
  const personaIntro = (dept && PERSONA_GREETINGS[dept]) ?? GENERIC_GREETING;

  return {
    id: 1,
    role: 'assistant',
    text: `${timeGreeting}! ${personaIntro} What can I help you with today?`,
    time: getTimeStr(),
  };
};

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [buildWelcomeMsg()],
  sessionId: null,
  isTyping: false,
  error: null,
  statusMessage: null,
  inputMode: 'text',
  showModes: false,
  recording: false,
  recordTime: 0,
  mediaPreview: null,
  selectedArtifact: null,
  sessions: [],
  tasks: [],
  activeTask: null,
  sessionTitles: {},

  addMessage: msg => set(s => ({messages: [...s.messages, msg]})),
  setIsTyping: v => set({isTyping: v}),
  setInputMode: v => set({inputMode: v}),
  setShowModes: v => set({showModes: v}),
  setRecording: v => set({recording: v}),
  setRecordTime: v => set({recordTime: v}),
  setMediaPreview: v => set({mediaPreview: v}),
  setSelectedArtifact: v => set({selectedArtifact: v}),
  setSessionId: id => set({sessionId: id}),
  clearError: () => set({error: null}),
  clearActiveTask: () => set({activeTask: null}),

  loadTitles: async () => {
    try {
      const raw = await AsyncStorage.getItem('@mz_chat_titles');
      if (raw) {
        set({sessionTitles: JSON.parse(raw)});
      }
    } catch {
      // Silent — keep empty map
    }
  },

  setSessionTitle: async (sessionId, title) => {
    const next = {...useChatStore.getState().sessionTitles, [sessionId]: title};
    set({sessionTitles: next});
    try {
      await AsyncStorage.setItem('@mz_chat_titles', JSON.stringify(next));
    } catch {
      // Silent
    }
  },

  sendToServer: async (text, mode, media, mediaUri) => {
    if (!text && !media) {
      return;
    }
    const {sessionId, messages} = get();
    const userTime = getTimeStr();

    // Capture auto-title from the first user message (before optimistic update)
    const isFirstUserMessage = messages.filter(m => m.role === 'user').length === 0;
    const autoTitle = (isFirstUserMessage && text) ? text.slice(0, 40) : null;

    // Optimistically add user message to the list
    set(s => ({
      messages: [
        ...s.messages,
        {
          id: Date.now(),
          role: 'user',
          text: text || '',
          time: userTime,
          type: mode,
          media: media || undefined,
        },
      ],
      isTyping: true,
      error: null,
      statusMessage: null,
    }));

    try {
      let response: ChatResponse;

      if (mode === 'url') {
        // URL mode: text field contains the URL the user pasted
        response = await sendUrlApi(text, undefined, sessionId);
      } else if (media && mediaUri && mode !== 'text' && mode !== 'speech') {
        // Real file upload via sendMediaApi
        const mimeType =
          mode === 'image' ? (media.mimeType || 'image/jpeg')
          : mode === 'video' ? 'video/mp4'
          : mode === 'audio' ? 'audio/m4a'
          : media.mimeType || 'application/octet-stream';
        response = await sendMediaApi(
          mediaUri,
          media.name,
          mimeType,
          mode as 'image' | 'video' | 'audio' | 'file',
          text || null,
          sessionId,
        );
      } else {
        // Text and speech modes → POST /chat/send
        response = await sendTextApi(text, sessionId);
      }

      // Add assistant response and update sessionId in one atomic set
      // Only create activeTask for background tasks the server explicitly queued
      const newActiveTask: TaskSummary | null =
        response.task_id && response.status === 'queued'
          ? {
              id: response.task_id,
              session_id: response.session_id ?? null,
              title: text.slice(0, 80),
              status: 'queued',
              queue_name: 'background',
              created_at: new Date().toISOString(),
            }
          : null;

      // Wire up WS task_complete notification for background tasks
      if (newActiveTask) {
        const onTaskComplete = async (data: {
          task_id: string;
          session_id: string;
          message: string;
          response?: string;
          file_url: string | null;
        }) => {
          // 1. Extract response text — use WS payload first, fallback to API fetch
          let responseText = data.response || '';
          if (!responseText) {
            try {
              const taskData = await getTaskByIdApi(data.task_id);
              responseText = (taskData as any).result?.response || data.message || '';
            } catch {
              responseText = data.message || 'Task completed.';
            }
          }

          // 2. Add as assistant message if we have text
          if (responseText) {
            const newMsg: Message = {
              id: Date.now(),
              role: 'assistant',
              text: responseText,
              time: getTimeStr(),
            };
            set(s => ({messages: [...s.messages, newMsg]}));
          }

          // 3. Update activeTask to completed (triggers 3s banner dismiss)
          set(s => ({
            activeTask: s.activeTask?.id === data.task_id
              ? {...s.activeTask, status: 'completed' as const}
              : s.activeTask,
          }));
          get().loadTasks();
        };
        if (mzWs.isConnected) {
          // Already connected — just update the callback
          mzWs.setCallbacks({onTaskComplete});
        } else {
          // Connect and register callback; polling is the fallback if this fails
          mzWs.connect({onTaskComplete}).catch(() => {});
        }
      }

      // Only add an assistant message for synchronous (non-queued) responses.
      // For queued responses, the task banner handles UX; result arrives via WS.
      if (!newActiveTask) {
        const newAgentUsed = response.agent_used || undefined;
        set(s => {
          // Find the previous assistant message (non-system) to detect agent change
          const prevAssistant = [...s.messages].reverse().find(
            m => m.role === 'assistant' && !m.isSystem,
          );
          const prevAgent = prevAssistant?.agentUsed;
          const agentChanged =
            newAgentUsed &&
            prevAssistant !== undefined &&
            prevAgent !== newAgentUsed;

          const newMsg: Message = {
            id: Date.now(),
            role: 'assistant',
            text: response.response || 'Task completed.',
            time: getTimeStr(),
            artifacts: (response.artifacts?.length ?? 0) > 0 ? response.artifacts : undefined,
            tools: (response.tools_used?.length ?? 0) > 0 ? response.tools_used : undefined,
            agentUsed: newAgentUsed,
          };

          // Insert handoff divider if the responding agent changed
          const divider: Message | null = agentChanged
            ? {
                id: Date.now() - 1,
                role: 'system',
                text: `${DEPT_TO_PERSONA[newAgentUsed!] || newAgentUsed} joined the conversation`,
                time: getTimeStr(),
                isSystem: true,
                agentUsed: newAgentUsed,
              }
            : null;

          return {
            sessionId: response.session_id,
            messages: [
              ...s.messages,
              ...(divider ? [divider] : []),
              newMsg,
            ],
            isTyping: false,
            statusMessage: null,
          };
        });
      } else {
        // Queued: clear typing, store session ID, set active task banner
        set({
          isTyping: false,
          statusMessage: null,
          activeTask: newActiveTask,
          sessionId: response.session_id || null,  // link chat to the queued session
        });
      }

      // Auto-set title from first user message if no custom title exists yet
      if (autoTitle && response.session_id) {
        const {sessionTitles} = get();
        if (!sessionTitles[response.session_id]) {
          get().setSessionTitle(response.session_id, autoTitle);
        }
      }
    } catch (e: unknown) {
      const message =
        e instanceof Error ? e.message : 'Failed to send message. Please try again.';
      set({isTyping: false, error: message, statusMessage: null});
    }
  },

  sendArtifactToServer: async (artifactId, message) => {
    const {sessionId, messages, selectedArtifact} = get();
    const artifact = selectedArtifact;
    const userTime = getTimeStr();

    const isFirstUserMessage = messages.filter(m => m.role === 'user').length === 0;
    const autoTitle = (isFirstUserMessage && message) ? message.slice(0, 40) : null;

    set(s => ({
      messages: [
        ...s.messages,
        {
          id: Date.now(),
          role: 'user',
          text: message || '',
          time: userTime,
          type: 'myfiles',
          media: artifact
            ? {type: 'myfiles', name: artifact.filename, size: 'From My Files', emoji: '📂'}
            : undefined,
        },
      ],
      isTyping: true,
      error: null,
      statusMessage: null,
    }));

    try {
      const response = await sendArtifactApi(artifactId, message, sessionId);
      const newAgentUsed = response.agent_used || undefined;

      set(s => {
        const prevAssistant = [...s.messages].reverse().find(
          m => m.role === 'assistant' && !m.isSystem,
        );
        const prevAgent = prevAssistant?.agentUsed;
        const agentChanged =
          newAgentUsed &&
          prevAssistant !== undefined &&
          prevAgent !== newAgentUsed;

        const newMsg: Message = {
          id: Date.now(),
          role: 'assistant',
          text: response.response,
          time: getTimeStr(),
          artifacts: (response.artifacts?.length ?? 0) > 0 ? response.artifacts : undefined,
          tools: (response.tools_used?.length ?? 0) > 0 ? response.tools_used : undefined,
          agentUsed: newAgentUsed,
        };

        const divider: Message | null = agentChanged
          ? {
              id: Date.now() - 1,
              role: 'system',
              text: `${DEPT_TO_PERSONA[newAgentUsed!] || newAgentUsed} joined the conversation`,
              time: getTimeStr(),
              isSystem: true,
              agentUsed: newAgentUsed,
            }
          : null;

        return {
          sessionId: response.session_id,
          messages: [
            ...s.messages,
            ...(divider ? [divider] : []),
            newMsg,
          ],
          isTyping: false,
          statusMessage: null,
        };
      });

      if (autoTitle && response.session_id) {
        const {sessionTitles} = get();
        if (!sessionTitles[response.session_id]) {
          get().setSessionTitle(response.session_id, autoTitle);
        }
      }
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : 'Failed to send message. Please try again.';
      set({isTyping: false, error: msg, statusMessage: null});
    }
  },

  loadSessions: async () => {
    try {
      const result = await getSessionsApi();
      set({sessions: result.sessions});
    } catch {
      // Silent — HistoryScreen shows empty state on failure
    }
  },

  loadTasks: async () => {
    try {
      const result = await getTasksApi();
      set({tasks: result.tasks});
    } catch (err) {
      console.warn('[chatStore] loadTasks failed:', err);
    }
  },

  pollActiveTask: async (sessionId: string) => {
    try {
      const result = await getActiveTasksApi();
      // Guard: discard response if session changed while the request was in-flight
      // (e.g., user tapped "+" and resetChat() ran between the call and the response)
      if (get().sessionId !== sessionId) { return; }
      const task = result.tasks.find(t => t.session_id === sessionId) ?? null;

      // If task just completed and has a response, add to chat
      if (task && (task.status === 'completed' || task.status === 'failed')) {
        const responseText = task.result?.response || '';
        if (responseText) {
          const existing = get().messages;
          const alreadyShown = existing.some(m => m.role === 'assistant' && m.text === responseText);
          if (!alreadyShown) {
            const newMsg: Message = {
              id: Date.now(),
              role: 'assistant',
              text: responseText,
              time: getTimeStr(),
            };
            set(s => ({messages: [...s.messages, newMsg]}));
          }
        }
      }

      set({activeTask: task});
    } catch (err) {
      console.warn('[chatStore] pollActiveTask failed:', err);
    }
  },

  loadHistory: async (sessionId: string) => {
    try {
      const result = await getHistoryApi(sessionId);
      const messages: Message[] = result.messages.map((m, i) => ({
        id: Date.now() + i,
        role: m.role,
        text: m.content,
        time: new Date(m.timestamp).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
        }),
      }));
      // Restore task banner if this session has a background task.
      // tasks[] is already populated by loadTasks() called in HistoryScreen
      // before navigation, so the find is synchronous and reliable.
      const sessionTask = get().tasks.find(t => t.session_id === sessionId) ?? null;
      set({messages, sessionId, activeTask: sessionTask});
    } catch {
      // Silent — keep current messages
    }
  },

  resetChat: () =>
    set({
      messages: [buildWelcomeMsg()],
      sessionId: null,
      isTyping: false,
      error: null,
      statusMessage: null,
      inputMode: 'text',
      showModes: false,
      recording: false,
      recordTime: 0,
      mediaPreview: null,
      selectedArtifact: null,
      activeTask: null,
    }),

  toggleFavorite: async (sessionId) => {
    const {sessions} = get();
    const idx = sessions.findIndex(s => s.session_id === sessionId);
    if (idx === -1) { return; }
    const original = sessions[idx].is_favorite;
    const next = sessions.map((s, i) =>
      i === idx ? {...s, is_favorite: !original} : s
    );
    set({sessions: next});
    try {
      await patchSessionApi(sessionId, {is_favorite: !original});
    } catch {
      set({sessions});
    }
  },

  toggleArchive: async (sessionId) => {
    const {sessions} = get();
    const idx = sessions.findIndex(s => s.session_id === sessionId);
    if (idx === -1) { return; }
    const original = sessions[idx].is_archived;
    const next = sessions.map((s, i) =>
      i === idx ? {...s, is_archived: !original} : s
    );
    set({sessions: next});
    try {
      await patchSessionApi(sessionId, {is_archived: !original});
    } catch {
      set({sessions});
    }
  },
}));
