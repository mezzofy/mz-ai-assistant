import {create} from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  sendTextApi,
  sendUrlApi,
  sendMediaApi,
  getSessionsApi,
  getHistoryApi,
  ChatResponse,
  SessionSummary,
} from '../api/chat';

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
  role: 'user' | 'assistant';
  text: string;
  time: string;
  type?: string;
  media?: MediaInfo;
  artifacts?: Artifact[];
  tools?: string[];
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
  sessions: SessionSummary[];
  sessionTitles: Record<string, string>;
  // Primitive setters (used by ChatScreen UI)
  addMessage: (msg: Message) => void;
  setIsTyping: (v: boolean) => void;
  setInputMode: (v: string) => void;
  setShowModes: (v: boolean) => void;
  setRecording: (v: boolean) => void;
  setRecordTime: (v: number) => void;
  setMediaPreview: (v: MediaInfo | null) => void;
  setSessionId: (id: string | null) => void;
  clearError: () => void;
  // Session title management
  loadTitles: () => Promise<void>;
  setSessionTitle: (sessionId: string, title: string) => Promise<void>;
  // API actions
  sendToServer: (text: string, mode: string, media: MediaInfo | null, mediaUri?: string | null) => Promise<void>;
  loadSessions: () => Promise<void>;
  loadHistory: (sessionId: string) => Promise<void>;
  resetChat: () => void;
};

const getTimeStr = () =>
  new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});

const WELCOME_MSG: Message = {
  id: 1,
  role: 'assistant',
  text: 'Good morning! How can I help the team today?',
  time: getTimeStr(),
};

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [WELCOME_MSG],
  sessionId: null,
  isTyping: false,
  error: null,
  statusMessage: null,
  inputMode: 'text',
  showModes: false,
  recording: false,
  recordTime: 0,
  mediaPreview: null,
  sessions: [],
  sessionTitles: {},

  addMessage: msg => set(s => ({messages: [...s.messages, msg]})),
  setIsTyping: v => set({isTyping: v}),
  setInputMode: v => set({inputMode: v}),
  setShowModes: v => set({showModes: v}),
  setRecording: v => set({recording: v}),
  setRecordTime: v => set({recordTime: v}),
  setMediaPreview: v => set({mediaPreview: v}),
  setSessionId: id => set({sessionId: id}),
  clearError: () => set({error: null}),

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
      set(s => ({
        sessionId: response.session_id,
        messages: [
          ...s.messages,
          {
            id: Date.now(),
            role: 'assistant',
            text: response.response,
            time: getTimeStr(),
            artifacts: response.artifacts.length > 0 ? response.artifacts : undefined,
            tools: response.tools_used.length > 0 ? response.tools_used : undefined,
          },
        ],
        isTyping: false,
        statusMessage: null,
      }));

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

  loadSessions: async () => {
    try {
      const result = await getSessionsApi();
      set({sessions: result.sessions});
    } catch {
      // Silent — HistoryScreen shows empty state on failure
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
      set({messages, sessionId});
    } catch {
      // Silent — keep current messages
    }
  },

  resetChat: () =>
    set({
      messages: [{...WELCOME_MSG, id: Date.now(), time: getTimeStr()}],
      sessionId: null,
      isTyping: false,
      error: null,
      statusMessage: null,
      inputMode: 'text',
      showModes: false,
      recording: false,
      recordTime: 0,
      mediaPreview: null,
    }),
}));
