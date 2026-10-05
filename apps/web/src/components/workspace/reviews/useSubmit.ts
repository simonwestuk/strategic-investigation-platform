"use client";

import { useState } from "react";
import type { ReviewResponseBody } from "@/lib/types";

export function useSubmit(onSubmit: (body: ReviewResponseBody) => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  async function run(body: ReviewResponseBody) {
    setBusy(true);
    setError(null);
    try {
      await onSubmit(body);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run };
}
