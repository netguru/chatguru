import { useEffect } from "react";
import type { MessageRole } from "../types/chat";
import { selectCurrentSession, useAppStore } from "../store/appStore";
import { getOrCreateVisitorId } from "../utils/visitorId";

interface ConversationDto {
  session_id: string;
  title: string;
  created_at: string;
}

interface HistoryMessageDto {
  role: string;
  content: string;
  trace_id?: string;
}

interface ValidHistoryMessageDto {
  role: MessageRole;
  content: string;
  trace_id?: string;
}

function isMessageRole(role: string): role is MessageRole {
  return role === "user" || role === "assistant" || role === "system";
}

function hasValidRole(entry: HistoryMessageDto): entry is ValidHistoryMessageDto {
  return isMessageRole(entry.role);
}

export function usePersistedHistory() {
  const replaceSessions = useAppStore((s) => s.replaceSessions);
  const hydrateSessionHistory = useAppStore((s) => s.hydrateSessionHistory);
  const currentSession = useAppStore(selectCurrentSession);

  useEffect(() => {
    const controller = new AbortController();
    const visitorId = getOrCreateVisitorId();

    async function loadConversations() {
      try {
        const params = new URLSearchParams({ visitor_id: visitorId });
        const response = await fetch(`/conversations?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!response.ok) return;

        const conversations = (await response.json()) as ConversationDto[];
        replaceSessions(
          conversations.map((conversation) => ({
            id: conversation.session_id,
            title: conversation.title,
            createdAt: conversation.created_at,
            messages: [],
            history: [],
            isHydrated: false,
          }))
        );
      } catch {
      }
    }

    void loadConversations();

    return () => controller.abort();
  }, [replaceSessions]);

  useEffect(() => {
    if (!currentSession || currentSession.isHydrated) return;

    const sessionId = currentSession.id;
    const controller = new AbortController();
    const visitorId = getOrCreateVisitorId();

    async function loadHistory() {
      try {
        const params = new URLSearchParams({
          visitor_id: visitorId,
          session_id: sessionId,
        });
        const response = await fetch(`/history?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!response.ok) return;

        const rawHistory = (await response.json()) as HistoryMessageDto[];
        const history = rawHistory
          .filter(hasValidRole)
          .map((entry) => ({
            role: entry.role,
            content: entry.content,
            ...(entry.trace_id ? { traceId: entry.trace_id } : {}),
          }));

        hydrateSessionHistory(sessionId, history);
      } catch {
      }
    }

    void loadHistory();

    return () => controller.abort();
  }, [currentSession, hydrateSessionHistory]);
}
