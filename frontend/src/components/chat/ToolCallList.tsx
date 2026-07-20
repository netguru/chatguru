import { CaretRightIcon, WrenchIcon } from "@phosphor-icons/react";
import { useState } from "react";
import type { ToolCall } from "../../types/chat";
import { cn } from "../../utils/utils";
import { Loader } from "../ui/loader";

interface Props {
  toolCalls: ToolCall[];
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function ToolCallChip({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-m border border-border-neutral-soft bg-surface-neutral-soft">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-t3 text-text-primary cursor-pointer"
      >
        <WrenchIcon weight="bold" className="size-3.5 shrink-0 text-text-secondary" />
        <span className="font-medium">{call.name}</span>
        {call.status === "running" ? (
          <Loader className="ms-auto basis-auto [&>span]:size-1.5" />
        ) : (
          <CaretRightIcon
            weight="bold"
            className={cn("ms-auto size-3.5 transition-transform", open && "rotate-90")}
          />
        )}
      </button>
      {open && (
        <div className="border-t border-border-neutral-soft px-3 py-2 text-t3 text-text-secondary">
          <div className="mb-1 font-medium">args</div>
          <pre className="mb-2 max-h-40 overflow-auto whitespace-pre-wrap break-words">
            {formatValue(call.args)}
          </pre>
          {call.status === "done" && (
            <>
              <div className="mb-1 font-medium">result</div>
              <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words">
                {formatValue(call.result)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolCallList({ toolCalls }: Props) {
  if (!toolCalls.length) return null;
  return (
    <div className="mb-3 flex flex-col gap-1.5">
      {toolCalls.map((call, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: calls have no id and are append-only within a turn
        <ToolCallChip key={`${call.name}-${i}`} call={call} />
      ))}
    </div>
  );
}
