import { useEffect, useState } from "react";
import type { LlmModel, LlmModelProvider, LlmModelsResponse } from "../types/chat";

const STORAGE_KEY = "chatguru_selected_model";

/**
 * Fetches the list of available LiteLLM models from GET /models once on mount.
 *
 * When the LiteLLM provider is not active the backend returns an empty
 * providers list, so `providers` stays empty and consumers render nothing —
 * zero visual change for Azure/OpenAI deployments.
 *
 * The selected model ID is persisted in localStorage so the user's choice
 * survives refreshes. It defaults to the first model in the list.
 */
export function useModels() {
  const [providers, setProviders] = useState<LlmModelProvider[]>([]);
  const [selectedModelId, setSelectedModelIdState] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/models")
      .then((r) => r.json())
      .then((data: LlmModelsResponse) => {
        if (cancelled) return;
        const nextProviders = data.providers ?? [];
        setProviders(nextProviders);

        const allModels: LlmModel[] = nextProviders.flatMap((p) => p.models);
        if (allModels.length === 0) return;

        const stored = window.localStorage.getItem(STORAGE_KEY);
        const isValid = stored !== null && allModels.some((m) => m.id === stored);
        setSelectedModelIdState(isValid ? stored : allModels[0].id);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setSelectedModelId = (id: string) => {
    setSelectedModelIdState(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  };

  return { providers, selectedModelId, setSelectedModelId };
}
