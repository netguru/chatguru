import { useState } from "react";
import { getOrCreateVisitorId } from "../utils/visitorId";

interface FeedbackPayload {
  trace_id: string;
  visitor_id: string;
  value: 0 | 1;
  comment?: string;
}

interface UseFeedbackResult {
  submitFeedback: (traceId: string, value: 0 | 1, comment?: string) => Promise<void>;
  isSubmitting: boolean;
}

export function useFeedback(): UseFeedbackResult {
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submitFeedback(traceId: string, value: 0 | 1, comment?: string): Promise<void> {
    setIsSubmitting(true);
    try {
      const payload: FeedbackPayload = {
        trace_id: traceId,
        visitor_id: getOrCreateVisitorId(),
        value,
      };
      if (comment) payload.comment = comment;

      const res = await fetch("/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(`Failed to submit feedback: ${res.status} ${res.statusText}`);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return { submitFeedback, isSubmitting };
}
