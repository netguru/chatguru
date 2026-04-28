import { useState } from "react";

interface FeedbackPayload {
  trace_id: string;
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
      const payload: FeedbackPayload = { trace_id: traceId, value };
      if (comment) payload.comment = comment;

      console.debug("[useFeedback] Submitting feedback:", payload);
      const res = await fetch("/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        console.error("[useFeedback] Feedback submission failed:", res.status, body);
      } else {
        console.debug("[useFeedback] Response:", res.status, body);
      }
    } catch (err) {
      console.error("[useFeedback] Failed to submit feedback:", err);
    } finally {
      setIsSubmitting(false);
    }
  }

  return { submitFeedback, isSubmitting };
}
