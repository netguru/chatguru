import { create } from "zustand";
import type { ChatMessage, HistoryMessage, Source, VectorDbType } from "../types/chat";

// ─── Session ─────────────────────────────────────────────────────────────────

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
  isHydrated: boolean;
  /**
   * Parallel history array sent as context to the backend WS.
   * Separate from `messages` (which is the UI list) because the backend
   * history format is simpler: { role, content } without UI-specific fields.
   */
  history: HistoryMessage[];
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 11);
}

function createSession(): Session {
  return {
    id: generateId(),
    title: "New conversation",
    createdAt: new Date().toISOString(),
    messages: [],
    isHydrated: true,
    history: [],
  };
}

// ─── State shape ─────────────────────────────────────────────────────────────

interface AppState {
  // WebSocket connection
  isConnected: boolean;
  isStreaming: boolean;

  // Backend settings
  vectorDbType: VectorDbType;

  // Conversations
  sessions: Session[];
  currentSessionId: string | null;

  // ── Connection actions ────────────────────────────────────────────────────
  setConnected: (v: boolean) => void;
  setStreaming: (v: boolean) => void;

  // ── Settings actions ──────────────────────────────────────────────────────
  setVectorDbType: (type: VectorDbType) => void;

  // ── Message actions (operate on the current session) ─────────────────────
  addUserMessage: (msg: ChatMessage) => void;
  addAssistantPlaceholder: (msg: ChatMessage) => void;
  appendTokenToLastMessage: (token: string) => void;
  finalizeLastMessage: (content: string, sources: Source[] | null) => void;
  markLastMessageError: (content: string) => void;
  addToHistory: (entry: HistoryMessage) => void;

  // ── Layout ────────────────────────────────────────────────────────────────
  inputAreaHeight: number;
  setInputAreaHeight: (h: number) => void;

  // ── Sources panel ─────────────────────────────────────────────────────────
  sourcesPanelOpen: boolean;
  sourcesPanelSources: Source[];
  openSourcesPanel: (sources: Source[]) => void;
  closeSourcesPanel: () => void;

  // ── Session actions ───────────────────────────────────────────────────────
  /** Switch to draft mode — session is created lazily on first message */
  startNewSession: () => void;
  /** Switch to an existing session by id (for sidebar history) */
  loadSession: (id: string) => void;
  /** Clear messages in the current session and reset its WS session id */
  clearCurrentSession: () => void;
  replaceSessions: (sessions: Session[]) => void;
  hydrateSessionHistory: (sessionId: string, history: HistoryMessage[]) => void;
  updateSessionTitle: (sessionId: string, title: string) => void;
}

// ─── Store ───────────────────────────────────────────────────────────────────

export const useAppStore = create<AppState>((set) => ({
  isConnected: false,
  isStreaming: false,
  vectorDbType: "sqlite",
  sessions: [],
  currentSessionId: null,
  inputAreaHeight: 0,
  sourcesPanelOpen: false,
  sourcesPanelSources: [],

  // Connection
  setConnected: (v) => set({ isConnected: v }),
  setInputAreaHeight: (h) => set({ inputAreaHeight: h }),
  setStreaming: (v) => set({ isStreaming: v }),

  // Settings
  setVectorDbType: (type) => set({ vectorDbType: type }),

  // Messages
  addUserMessage: (msg) =>
    set((state) => {
      if (state.currentSessionId === null) {
        // Lazy session creation — first message triggers it
        const session: Session = {
          ...createSession(),
          title: msg.content.slice(0, 40),
          messages: [msg],
        };
        return { sessions: [session, ...state.sessions], currentSessionId: session.id };
      }
      return {
        sessions: state.sessions.map((s) =>
          s.id === state.currentSessionId
            ? {
                ...s,
                // Auto-title: first user message, max 40 chars
                title: s.messages.length === 0 ? msg.content.slice(0, 40) : s.title,
                messages: [...s.messages, msg],
              }
            : s
        ),
      };
    }),

  addAssistantPlaceholder: (msg) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === state.currentSessionId ? { ...s, messages: [...s.messages, msg] } : s
      ),
    })),

  appendTokenToLastMessage: (token) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== state.currentSessionId) return s;
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (!last?.isStreaming) return s;
        msgs[msgs.length - 1] = { ...last, content: last.content + token };
        return { ...s, messages: msgs };
      }),
    })),

  finalizeLastMessage: (content, sources) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== state.currentSessionId) return s;
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (!last?.isStreaming) return s;
        msgs[msgs.length - 1] = {
          ...last,
          content,
          sources: sources ?? undefined,
          isStreaming: false,
        };
        return { ...s, messages: msgs };
      }),
    })),

  markLastMessageError: (content) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== state.currentSessionId) return s;
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (!last?.isStreaming) return s;
        msgs[msgs.length - 1] = { ...last, content, isStreaming: false };
        return { ...s, messages: msgs };
      }),
    })),

  addToHistory: (entry) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === state.currentSessionId ? { ...s, history: [...s.history, entry] } : s
      ),
    })),

  // Sessions
  startNewSession: () => set({ currentSessionId: null }),

  loadSession: (id) => set({ currentSessionId: id }),

  // Sources panel
  openSourcesPanel: (sources) => set({ sourcesPanelOpen: true, sourcesPanelSources: sources }),
  closeSourcesPanel: () => set({ sourcesPanelOpen: false, sourcesPanelSources: [] }),

  clearCurrentSession: () =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== state.currentSessionId),
      currentSessionId: null,
    })),

  replaceSessions: (fetchedSessions) =>
    set((state) => {
      // Preserve any locally-created sessions (isHydrated === true) that are not
      // present in the fetched list. These were started while loadConversations()
      // was in-flight and would otherwise be silently dropped by a naive replace.
      const fetchedIds = new Set(fetchedSessions.map((s) => s.id));
      const localSessions = state.sessions.filter((s) => s.isHydrated && !fetchedIds.has(s.id));
      const mergedSessions = [...localSessions, ...fetchedSessions];
      return {
        sessions: mergedSessions,
        currentSessionId:
          state.currentSessionId && mergedSessions.some((s) => s.id === state.currentSessionId)
            ? state.currentSessionId
            : mergedSessions[0]?.id ?? null,
      };
    }),

  hydrateSessionHistory: (sessionId, history) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        const hydratedMessages: ChatMessage[] = history.map((entry) => ({
          id: crypto.randomUUID(),
          role: entry.role,
          content: entry.content,
        }));
        return {
          ...s,
          messages: hydratedMessages,
          history,
          isHydrated: true,
        };
      }),
    })),

  updateSessionTitle: (sessionId, title) =>
    set((state) => ({
      sessions: state.sessions.map((s) => (s.id === sessionId ? { ...s, title } : s)),
    })),
}));

// ─── Selectors ────────────────────────────────────────────────────────────────

export const selectCurrentSession = (state: AppState): Session | undefined =>
  state.sessions.find((s) => s.id === state.currentSessionId);

const EMPTY_MESSAGES: ChatMessage[] = [];
const EMPTY_HISTORY: HistoryMessage[] = [];

export const selectCurrentMessages = (state: AppState): ChatMessage[] =>
  selectCurrentSession(state)?.messages ?? EMPTY_MESSAGES;

export const selectCurrentHistory = (state: AppState): HistoryMessage[] =>
  selectCurrentSession(state)?.history ?? EMPTY_HISTORY;
