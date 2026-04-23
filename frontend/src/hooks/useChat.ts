import { useCallback, useEffect, useRef } from "react";
import { selectCurrentHistory, useAppStore } from "../store/appStore";
import type { WsEndEvent, WsErrorEvent, WsEvent, WsTokenEvent } from "../types/chat";

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
  } = useAppStore();

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Prevents onclose from scheduling a reconnect after the hook unmounts.
  const shouldReconnectRef = useRef(true);

  // Refs for values consumed inside WS callbacks (avoids stale closures while
  // keeping connect() stable and useable as an effect dependency).
  const isStreamingRef = useRef(isStreaming);
  isStreamingRef.current = isStreaming;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = import.meta.env.VITE_WS_HOST ?? window.location.host;
    const ws = new WebSocket(`${protocol}//${host}${WS_PATH}`);
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
        finalizeLastMessage(endEvent.content, endEvent.sources ?? null);
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

      // Snapshot prior turns before adding the current user message, then append
      // the current user turn so the backend receives the full transcript with the
      // current turn as the last entry (required by the ChatMessage contract).
      const priorHistory = selectCurrentHistory(useAppStore.getState());
      const messages = [...priorHistory, { role: "user" as const, content: text }];

      addUserMessage({ id: crypto.randomUUID(), role: "user", content: text });
      addToHistory({ role: "user", content: text });

      // Read currentSessionId AFTER addUserMessage — the first-ever message triggers
      // lazy session creation inside the store (synchronous Zustand set), so reading
      // before would yield null and send session_id: null to the backend.
      const { currentSessionId, vectorDbType } = useAppStore.getState();

      // Create the assistant placeholder immediately — backend sends token events
      // directly without a preceding 'start' event.
      setStreaming(true);
      addAssistantPlaceholder({
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        isStreaming: true,
      });

      wsRef.current.send(
        JSON.stringify({
          session_id: currentSessionId,
          messages,
          vector_db_type: vectorDbType,
          platform: "web",
        })
      );
    },
    [addUserMessage, addToHistory, setStreaming, addAssistantPlaceholder]
  );

  return { sendMessage };
}
