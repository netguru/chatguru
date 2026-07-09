import { CaretDownIcon, CheckIcon } from "@phosphor-icons/react";
import type { LlmModelProvider } from "../../types/chat";
import { cn } from "../../utils/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

interface Props {
  providers: LlmModelProvider[];
  selectedModelId: string | null;
  onSelect: (id: string) => void;
  disabled?: boolean;
}

/**
 * Per-request model picker shown in the chat input area. Rendered only when the
 * LiteLLM provider is active (i.e. `providers` is non-empty). Models are grouped
 * by their provider name.
 */
export function ModelSelector({ providers, selectedModelId, onSelect, disabled }: Props) {
  if (providers.length === 0) return null;

  const selectedModel = providers.flatMap((p) => p.models).find((m) => m.id === selectedModelId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2.5 py-1",
            "text-t3 text-text-secondary",
            "hover:bg-surface-hover-interactive-medium hover:text-text-primary",
            "disabled:pointer-events-none disabled:opacity-50",
            "cursor-pointer transition-colors"
          )}
        >
          <span className="max-w-[160px] truncate">{selectedModel?.label ?? "Select model"}</span>
          <CaretDownIcon weight="bold" className="size-3 shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top">
        {providers.map((provider) => (
          <DropdownMenuGroup key={provider.name}>
            <DropdownMenuLabel className="text-t4 text-text-tertiary">
              {provider.name}
            </DropdownMenuLabel>
            {provider.models.map((model) => (
              <DropdownMenuItem
                key={model.id}
                onSelect={() => onSelect(model.id)}
                className="justify-between"
              >
                <span className="truncate">{model.label}</span>
                {model.id === selectedModelId && (
                  <CheckIcon weight="bold" className="size-3 shrink-0" />
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
