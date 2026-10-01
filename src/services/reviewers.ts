import { useCallback, useEffect, useState } from "react";
import { request } from "./api";

export type Reviewer = {
  id: string;
  displayName: string;
  role: string;
  createdAt?: string | null;
};

const STORAGE_KEY = "np.reviewer";
export const DEFAULT_REVIEWER_ID = "reviewer_demo";

export async function listReviewers(): Promise<Reviewer[]> {
  return request<Reviewer[]>("/reviewers");
}

export async function createReviewer(id: string, displayName: string): Promise<Reviewer> {
  return request<Reviewer>("/reviewers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, display_name: displayName }),
  });
}

export function loadActiveReviewerId(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_REVIEWER_ID;
  } catch {
    return DEFAULT_REVIEWER_ID;
  }
}

export function saveActiveReviewerId(id: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // localStorage unavailable — fall back to the default identity.
  }
}

export function useReviewers() {
  const [reviewers, setReviewers] = useState<Reviewer[] | null>(null);
  const [activeId, setActiveId] = useState<string>(() => loadActiveReviewerId());
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await listReviewers();
      setReviewers(list);
      if (!list.some((r) => r.id === loadActiveReviewerId()) && list.length > 0) {
        saveActiveReviewerId(list[0].id);
        setActiveId(list[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load reviewers.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const select = (id: string) => {
    saveActiveReviewerId(id);
    setActiveId(id);
  };

  const active = reviewers?.find((r) => r.id === activeId) ?? null;

  return { reviewers, active, activeId, select, refresh, error };
}
