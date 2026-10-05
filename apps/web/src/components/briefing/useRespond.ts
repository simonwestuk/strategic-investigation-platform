"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ReviewResponseBody } from "@/lib/types";

/** Submit a review response, then refresh the investigation. */
export function useRespond(investigationId: string, reviewId: string, reload: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (body: ReviewResponseBody) => {
    setBusy(true);
    setError(null);
    try {
      await api.respondToReview(investigationId, reviewId, body);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, submit };
}
