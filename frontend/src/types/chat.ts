export type VectorDbType = "sqlite" | "mongodb";

export type MessageRole = "user" | "assistant" | "system";

/** A file attachment persisted on the server and retrievable via GET /attachments/{id}. */
export interface StoredAttachment {
  id: string;
  name: string;
  mime_type: string;
}

export interface HistoryMessage {
  role: MessageRole;
  content: string;
  traceId?: string;
  sources?: Source[];
  /**
   * IDs of pre-stored attachments (images via POST /upload-attachment,
   * documents via POST /process-document). Outbound only — sent to the backend.
   */
  attachment_ids?: string[];
  /** Server-persisted attachment metadata (inbound only — received from /history). */
  storedAttachments?: StoredAttachment[];
}

export interface Source {
  file?: string;
  pages?: number[];
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
  /** Base64 data-URLs for images attached to user messages (live chat only). */
  imageUrls?: string[];
  /** Server-persisted attachments — shown in both live chat (after end frame) and history. */
  storedAttachments?: StoredAttachment[];
}

// Outbound WebSocket message — matches backend ChatMessage schema.
// `messages` must be the full conversation with the current user turn as the last entry.
export interface WsOutboundMessage {
  session_id?: string;
  visitor_id: string;
  messages: HistoryMessage[];
  /** LiteLLM model ID for this request. Only sent when the LiteLLM provider is active. */
  model?: string;
}

/** A single selectable LiteLLM model. Matches backend LiteLLMModel. */
export interface LlmModel {
  label: string;
  id: string;
}

/** A provider group of models. Matches backend LiteLLMProvider. */
export interface LlmModelProvider {
  name: string;
  models: LlmModel[];
}

/** Response shape of GET /models. Matches backend LiteLLMModelsConfig. */
export interface LlmModelsResponse {
  providers: LlmModelProvider[];
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

// Raw source shape sent by the backend in the "end" WebSocket frame.
// Field names differ from the frontend Source type — useChat maps between them.
export interface BackendSource {
  source_id: string;
  source_uri?: string | null;
  title?: string | null;
  chunk_id?: string | null;
  source_type?: string | null;
  page?: number | null;
}

export interface WsEndEvent extends WsBaseEvent {
  type: "end";
  content: string;
  trace_id?: string;
  sources?: BackendSource[] | null;
  /** Attachments stored by the backend for the preceding user message. */
  user_attachments?: StoredAttachment[];
}

export interface WsErrorEvent extends WsBaseEvent {
  type: "error";
  content: string;
}

export type WsEvent = WsBaseEvent | WsTokenEvent | WsEndEvent | WsErrorEvent;
