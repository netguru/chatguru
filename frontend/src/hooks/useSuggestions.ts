import { useEffect, useState } from "react";

export function useSuggestions() {
  const [suggestions, setSuggestions] = useState<string[]>([
    "What topics are covered?",
    "Give me an overview",
    "Safety requirements",
    "Technical specifications",
  ]);

  useEffect(() => {
    fetch("/api/suggestions")
      .then((r) => r.json())
      .then((data: { suggestions: string[] }) => setSuggestions(data.suggestions))
      .catch(() => {});
  }, []);

  return suggestions;
}
