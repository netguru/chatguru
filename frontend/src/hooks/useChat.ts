import { useCallback, useEffect, useRef } from "react";
import { selectCurrentHistory, selectCurrentSession, useAppStore } from "../store/appStore";
import type {
  BackendSource,
  HistoryMessage,
  Source,
  WsEndEvent,
  WsErrorEvent,
  WsEvent,
  WsOutboundMessage,
  WsTokenEvent,
} from "../types/chat";

function mapBackendSources(raw: BackendSource[] | null | undefined): Source[] | null {
  if (!raw || raw.length === 0) return null;
  return raw.map((s) => ({
    file: s.source_uri ?? undefined,
    pages: s.page != null ? [s.page] : [],
  }));
}
import { getOrCreateVisitorId } from "../utils/visitorId";

// WebSocket path — matches backend @router.websocket("/ws") included without prefix.
// In development the Vite dev server proxies this path to the backend (see vite.config.ts).
const WS_PATH = "/ws";
const RECONNECT_DELAY_MS = 3000;

/**
 * Manages the WebSocket lifecycle and wires incoming events to the Zustand store.
 * Components should read state directly from `useAppStore` — this hook only
 * exposes `sendMessage` as the single imperative action.
 *
 * Backend event sequence: token → … → end  (or error at any point).
 * There is NO 'start' event — the assistant placeholder is created eagerly in
 * sendMessage so that the first token has a target message to append to.
 */
export function useChat() {
  const {
    isStreaming,
    setConnected,
    setStreaming,
    addUserMessage,
    addAssistantPlaceholder,
    appendTokenToLastMessage,
    finalizeLastMessage,
    markLastMessageError,
    addToHistory,
    updateSessionTitle,
  } = useAppStore();

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Prevents onclose from scheduling a reconnect after the hook unmounts.
  const shouldReconnectRef = useRef(true);

  // Refs for values consumed inside WS callbacks (avoids stale closures while
  // keeping connect() stable and useable as an effect dependency).
  const isStreamingRef = useRef(isStreaming);
  isStreamingRef.current = isStreaming;

  const requestConversationTitle = useCallback(
    async (sessionId: string, firstMessage: string, attempt = 0) => {
      const visitorId = getOrCreateVisitorId();
      try {
        const response = await fetch("/conversations/title", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            visitor_id: visitorId,
            session_id: sessionId,
            first_message: firstMessage,
          }),
        });
        if (response.status === 404 && attempt < 4) {
          window.setTimeout(() => {
            void requestConversationTitle(sessionId, firstMessage, attempt + 1);
          }, 150 * (attempt + 1));
          return;
        }
        if (!response.ok) return;

        const data = (await response.json()) as {
          session_id: string;
          title: string;
        };
        updateSessionTitle(data.session_id, data.title);
      } catch {
      }
    },
    [updateSessionTitle]
  );

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}${WS_PATH}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onclose = () => {
      setConnected(false);
      // If the connection dropped mid-stream, mark the placeholder as errored
      // so it doesn't stay stuck in a streaming state with no content.
      if (isStreamingRef.current) {
        setStreaming(false);
        markLastMessageError("Connection lost");
      } else {
        setStreaming(false);
      }
      if (shouldReconnectRef.current) {
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (event: MessageEvent) => {
      let data: WsEvent;
      try {
        data = JSON.parse(event.data as string) as WsEvent;
      } catch {
        // Malformed frame — discard silently to keep the handler alive.
        return;
      }

      if (data.type === "token") {
        appendTokenToLastMessage((data as WsTokenEvent).content);
      } else if (data.type === "end") {
        const endEvent = data as WsEndEvent;
        setStreaming(false);
        finalizeLastMessage(endEvent.content, mapBackendSources(endEvent.sources), endEvent.trace_id ?? null);
        addToHistory({ role: "assistant", content: endEvent.content });
      } else if (data.type === "error") {
        const errorEvent = data as WsErrorEvent;
        setStreaming(false);
        markLastMessageError(`Error: ${errorEvent.content}`);
      }
    };
  }, [
    setConnected,
    setStreaming,
    appendTokenToLastMessage,
    finalizeLastMessage,
    markLastMessageError,
    addToHistory,
  ]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();
    return () => {
      // Disable reconnect BEFORE closing so onclose doesn't schedule a new timer.
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || isStreamingRef.current)
        return;

      // Snapshot history BEFORE adding the current user message; we append the
      // current turn explicitly for the outbound payload.
      const historySnapshot = selectCurrentHistory(useAppStore.getState());

      addUserMessage({ id: crypto.randomUUID(), role: "user", content: text });
      addToHistory({ role: "user", content: text });

      // Read currentSessionId AFTER addUserMessage — the first-ever message triggers
      // lazy session creation inside the store (synchronous Zustand set), so reading
      // before would yield null and send session_id: null to the backend.
      const stateAfterAdd = useAppStore.getState();
      const { currentSessionId } = stateAfterAdd;
      const currentSession = selectCurrentSession(stateAfterAdd);
      const visitorId = getOrCreateVisitorId();
      const currentUserMessage: HistoryMessage = { role: "user", content: text };
      const outboundMessages = [...historySnapshot, currentUserMessage];
      // Only treat this as the first message in a new session when hydration has
      // completed (isHydrated === true). Persisted sessions that haven't finished
      // loading their history yet also have historySnapshot.length === 0, so
      // checking isHydrated prevents accidentally triggering title generation
      // (and sending an incomplete transcript) for those sessions.
      const isFirstMessageInSession =
        historySnapshot.length === 0 && currentSession?.isHydrated === true;

      // Create the assistant placeholder immediately — backend sends token events
      // directly without a preceding 'start' event.
      setStreaming(true);
      addAssistantPlaceholder({
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        isStreaming: true,
      });

      const payload: WsOutboundMessage = {
        session_id: currentSessionId ?? undefined,
        visitor_id: visitorId,
        messages: outboundMessages,
      };
      wsRef.current.send(JSON.stringify(payload));

      if (isFirstMessageInSession && currentSessionId) {
        void requestConversationTitle(currentSessionId, text);
      }
    },
    [
      addUserMessage,
      addToHistory,
      setStreaming,
      addAssistantPlaceholder,
      requestConversationTitle,
    ]
  );

  return { sendMessage };
}
