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

    s.resolveToolResultOnLastMessage("search_documents", "3 docs", true);
    expect(lastAssistant().toolCalls).toEqual([
      { name: "search_documents", args: { query: "pricing" }, result: "3 docs", status: "done" },
    ]);
  });

  it("marks a call failed when the backend reports ok=false", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("write_file", { path: "/tmp/x" });
    s.resolveToolResultOnLastMessage("write_file", "permission denied", false);
    expect(lastAssistant().toolCalls).toEqual([
      {
        name: "write_file",
        args: { path: "/tmp/x" },
        result: "permission denied",
        status: "failed",
      },
    ]);
  });

  it("matches results to calls by name in order", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("search_documents", { query: "a" });
    s.addToolCallToLastMessage("search_documents", { query: "b" });
    s.resolveToolResultOnLastMessage("search_documents", "first", true);
    const calls = lastAssistant().toolCalls ?? [];
    expect(calls[0]).toMatchObject({ args: { query: "a" }, result: "first", status: "done" });
    expect(calls[1]).toMatchObject({ args: { query: "b" }, status: "running" });
  });

  it("marks running tool calls as done when the stream errors", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("search_documents", { query: "pricing" });
    s.markLastMessageError("Something went wrong");
    const calls = lastAssistant().toolCalls ?? [];
    expect(calls[0].status).toBe("done");
    expect(calls[0].result).toBeUndefined();
  });

  it("marks running tool calls as done when the stream finalizes", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("search_documents", { query: "pricing" });
    s.finalizeLastMessage("All done", null);
    const calls = lastAssistant().toolCalls ?? [];
    expect(calls[0].status).toBe("done");
  });
});
