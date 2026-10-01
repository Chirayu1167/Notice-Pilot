import { request } from "./api";

export type DemoResetResult = {
  label: string;
  noticeId: string;
  stage: string;
  reconciliation: {
    status: string;
    noticeDifference: number;
    explainedAmount: number;
    unexplainedAmount: number;
  };
  agentRun: { id: string; status: string; decision: string };
  draftId: string | null;
};

export type DemoSupplementResult = DemoResetResult & {
  uploadedReturnId: string;
};

export const DEMO_LABEL = "SYNTHETIC DEMO DATA — NOT A REAL GST CASE";

export function isDemoMode(): boolean {
  if (typeof import.meta === "undefined") return false;
  const env = import.meta.env as Record<string, string | undefined>;
  return env.VITE_DEMO_MODE === "true" || Boolean(env.DEV);
}

export async function resetDemo(): Promise<DemoResetResult> {
  return request<DemoResetResult>("/demo/reset", { method: "POST" });
}

export async function supplementDemo(noticeId: string): Promise<DemoSupplementResult> {
  return request<DemoSupplementResult>(`/demo/supplement?notice_id=${encodeURIComponent(noticeId)}`, {
    method: "POST",
  });
}

export async function describeDemo(): Promise<{ label: string; noticeNumber: string; stages: string[] }> {
  return request("/demo/describe");
}
