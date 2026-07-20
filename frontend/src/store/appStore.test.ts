import { beforeEach, describe, expect, it } from "vitest";
import { selectCurrentMessages, useAppStore } from "./appStore";

function lastAssistant() {
  const msgs = selectCurrentMessages(useAppStore.getState());
  return msgs[msgs.length - 1];
}

describe("tool-call store actions", () => {
  beforeEach(() => {
    useAppStore.setState({ sessions: [], currentSessionId: null });
    const s = useAppStore.getState();
    s.addUserMessage({ id: "u1", role: "user", content: "hi" });
    s.addAssistantPlaceholder({ id: "a1", role: "assistant", content: "", isStreaming: true });
  });

  it("adds a running tool call then resolves it", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("search_documents", { query: "pricing" });
    expect(lastAssistant().toolCalls).toEqual([
      { name: "search_documents", args: { query: "pricing" }, status: "running" },
    ]);

    s.resolveToolResultOnLastMessage("search_documents", "3 docs");
    expect(lastAssistant().toolCalls).toEqual([
      { name: "search_documents", args: { query: "pricing" }, result: "3 docs", status: "done" },
    ]);
  });

  it("matches results to calls by name in order", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("search_documents", { query: "a" });
    s.addToolCallToLastMessage("search_documents", { query: "b" });
    s.resolveToolResultOnLastMessage("search_documents", "first");
    const calls = lastAssistant().toolCalls ?? [];
    expect(calls[0]).toMatchObject({ args: { query: "a" }, result: "first", status: "done" });
    expect(calls[1]).toMatchObject({ args: { query: "b" }, status: "running" });
  });
});
