import type React from "react";
import { useEffect, useRef, useState } from "react";
import { ChatInput } from "../components/chat/ChatInput";
import { ChatMessage } from "../components/chat/ChatMessage";
import { Chip, ChipLabel } from "../components/ui/chip";
import { Container } from "../components/ui/container";
import { useChat } from "../hooks/useChat";
import { useSuggestions } from "../hooks/useSuggestions";
import { selectCurrentMessages, useAppStore } from "../store/appStore";
import { cn } from "../utils/utils";

export function ChatPage() {
  const { sendMessage } = useChat();
  const [inputValue, setInputValue] = useState("");
  const suggestions = useSuggestions();

  const messages = useAppStore(selectCurrentMessages);
  const started = messages.length > 0;
  const inputAreaHeight = useAppStore((s) => s.inputAreaHeight);
  const setInputAreaHeight = useAppStore((s) => s.setInputAreaHeight);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputAreaRef = useRef<HTMLDivElement>(null);

  // biome-ignore lint/correctness/useExhaustiveDependencies: messages is an intentional trigger dep, not used inside the callback
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const el = inputAreaRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      setInputAreaHeight(entry.contentRect.height);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [setInputAreaHeight]);

  return (
    <div
      className="relative flex flex-col flex-1 overflow-hidden"
      style={
        {
          "--chat-input-height": `${inputAreaHeight + 16}px`,
        } as React.CSSProperties
      }
    >
      {/* ── Message list ── */}
      {started && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <Container className="flex flex-col gap-4">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </Container>
        </div>
      )}

      {/* Spacer — reserves space for the input area, height driven by --chat-input-height */}
      <div className="shrink-0 h-(--chat-input-height)" />

      {/* ── Input area (animates from center → bottom) ── */}
      <Container
        ref={inputAreaRef}
        className={cn(
          "py-0",
          "absolute left-1/2 -translate-x-1/2",
          "transition-[bottom,transform] duration-500 ease-in-out",
          started ? "bottom-4 translate-y-0" : "bottom-1/2 translate-y-1/2"
        )}
      >
        {!started && (
          <div
            className={cn(
              "w-full py-4",
              "flex flex-col items-start gap-1",
              "transition-opacity duration-300 ease-in-out"
            )}
          >
            <p className="text-h4 font-strong text-text-primary">Welcome!</p>
            <h2 className="text-h2 font-strong">What would you like to find out today?</h2>
          </div>
        )}

        <ChatInput
          onSend={(text) => {
            sendMessage(text);
            setInputValue("");
          }}
          value={inputValue}
          onValueChange={setInputValue}
        />

        <p className="mt-2 text-t4 text-text-tertiary">
          AI assistant can make mistakes. Consider verifying important information.
        </p>

        {!started && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {suggestions.map((suggestion) => (
              <Chip key={suggestion} onClick={() => setInputValue(suggestion)}>
                <ChipLabel>{suggestion}</ChipLabel>
              </Chip>
            ))}
          </div>
        )}
      </Container>
    </div>
  );
}
