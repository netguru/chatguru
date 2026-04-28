export type VectorDbType = "sqlite" | "mongodb";

export type MessageRole = "user" | "assistant" | "system";

export interface HistoryMessage {
  role: MessageRole;
  content: string;
}

export interface Source {
  file: string;
  pages: number[];
  url?: string;
  restricted?: boolean;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
  traceId?: string;
}

// Outbound WebSocket message — matches backend ChatMessage schema.
// `messages` must be the full conversation with the current user turn as the last entry.
export interface WsOutboundMessage {
  session_id?: string;
  visitor_id: string;
  messages: HistoryMessage[];
}

// Inbound WebSocket events — aligned with backend routes/chat.py
// Backend sends: token → … → end (or error). No 'start' event is emitted.
// Shape: { type, content, session_id } — no request_id / timestamp / error_code.
export type WsEventType = "token" | "end" | "error";

export interface WsBaseEvent {
  type: WsEventType;
  session_id: string;
}

export interface WsTokenEvent extends WsBaseEvent {
  type: "token";
  content: string;
}

export interface WsEndEvent extends WsBaseEvent {
  type: "end";
  content: string;
  trace_id?: string;
  // Backend does not currently send sources; reserved for future use.
  sources?: Source[] | null;
}

export interface WsErrorEvent extends WsBaseEvent {
  type: "error";
  content: string;
}

export type WsEvent = WsBaseEvent | WsTokenEvent | WsEndEvent | WsErrorEvent;
