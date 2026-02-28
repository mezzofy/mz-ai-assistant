import {create} from 'zustand';
import {
  sendTextApi,
  sendUrlApi,
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
  // API actions
  sendToServer: (text: string, mode: string, media: MediaInfo | null) => Promise<void>;
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

  addMessage: msg => set(s => ({messages: [...s.messages, msg]})),
  setIsTyping: v => set({isTyping: v}),
  setInputMode: v => set({inputMode: v}),
  setShowModes: v => set({showModes: v}),
  setRecording: v => set({recording: v}),
  setRecordTime: v => set({recordTime: v}),
  setMediaPreview: v => set({mediaPreview: v}),
  setSessionId: id => set({sessionId: id}),
  clearError: () => set({error: null}),

  sendToServer: async (text, mode, media) => {
    if (!text && !media) {
      return;
    }
    const {sessionId} = get();
    const userTime = getTimeStr();

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
      } else if (media && mode !== 'text' && mode !== 'speech') {
        // Media mode without real file picker (8B): describe attachment as text.
        // Real sendMediaApi with file URI will be wired in 8C with react-native-document-picker.
        const descriptionMsg = `[${mode}: ${media.name}]${text ? ' ' + text : ''}`;
        response = await sendTextApi(descriptionMsg, sessionId);
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
