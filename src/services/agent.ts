import type { AuditEvent, DraftReview, DraftVersion, ReplyDraft } from "../types";
import { API_BASE_URL, request } from "./api";

export type { AuditEvent, DraftReview, DraftVersion, ReplyDraft };

export type AgentStatus = {
  available: boolean;
  provider?: string;
  model?: string;
  message: string;
};

export type AgentStep = {
  sequence: number;
  tool: string;
  purpose: string;
  resultSummary: string;
  status: string;
  createdAt?: string | null;
};

export type AgentRun = {
  id: string;
  noticeId: string;
  status: string;
  decision?: string | null;
  reasoningSummary?: string | null;
  requiresHumanReview: boolean;
  provider?: string | null;
  model?: string | null;
  toolIterations: number;
  error?: string | null;
  draftId?: string | null;
  createdAt?: string | null;
  completedAt?: string | null;
  steps?: AgentStep[];
};

export type MissingEvidence = {
  type: string;
  source?: string | null;
  period?: string | null;
  amount?: number | null;
  reason: string;
};

export type NoticeEvidence = {
  verified: { evidenceId: string; source: string; period?: string | null; filename: string; rowCount: number }[];
  partial: { evidenceId: string; source: string; period?: string | null; filename: string; rowCount: number }[];
  missing: MissingEvidence[];
  reconciliationStatus?: string | null;
  unexplainedAmount?: number | null;
};

export async function getAgentStatus(): Promise<AgentStatus> {
  return request<AgentStatus>("/agent/status");
}

export async function getSystemStatus(): Promise<{
  backend: string;
  database: string;
  storage: boolean;
  agent: { available: boolean; provider?: string; model?: string };
  ruleVersion: string;
  appVersion: string;
}> {
  return request("/status");
}

export async function runAgent(noticeId: string): Promise<AgentRun> {
  return request<AgentRun>(`/notices/${encodeURIComponent(noticeId)}/agent/runs`, {
    method: "POST",
  });
}

export async function replanAgent(noticeId: string): Promise<{ reconciliation: unknown; agentRun: AgentRun }> {
  return request(`/notices/${encodeURIComponent(noticeId)}/agent/replan`, {
    method: "POST",
  });
}

export async function listAgentRuns(noticeId: string): Promise<AgentRun[]> {
  return request<AgentRun[]>(`/notices/${encodeURIComponent(noticeId)}/agent/runs`);
}

export async function getAgentRun(runId: string): Promise<AgentRun> {
  return request<AgentRun>(`/runs/${encodeURIComponent(runId)}`);
}

export async function getNoticeEvidence(noticeId: string): Promise<NoticeEvidence> {
  return request<NoticeEvidence>(`/notices/${encodeURIComponent(noticeId)}/evidence`);
}

export async function listReplyDrafts(noticeId: string): Promise<ReplyDraft[]> {
  return request<ReplyDraft[]>(`/notices/${encodeURIComponent(noticeId)}/reply-drafts`);
}

export async function getReplyDraft(draftId: string): Promise<ReplyDraft> {
  return request<ReplyDraft>(`/drafts/${encodeURIComponent(draftId)}`);
}

export async function saveReplyDraft(
  draftId: string,
  update: { content?: string; status?: string }
): Promise<ReplyDraft> {
  return request<ReplyDraft>(`/drafts/${encodeURIComponent(draftId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export async function getRuleMetadata(): Promise<{
  ruleVersion: string;
  sources: { notice_type: string; rule: string; relationship: string; formula: string; urls: string[] }[];
}> {
  return request("/rules");
}

export async function getReviewState(noticeId: string): Promise<{
  noticeId: string;
  draftId: string | null;
  review: DraftReview | null;
  reviewStatus: string;
  currentVersion: number;
  versions: DraftVersion[];
}> {
  return request(`/notices/${encodeURIComponent(noticeId)}/review`);
}

export async function submitReview(
  draftId: string,
  action: "APPROVE" | "REQUEST_CHANGES" | "REJECT",
  comment: string,
  reviewerId?: string
): Promise<{
  reviewId: string;
  draftId: string;
  version: number;
  status: string;
  comment: string;
  reviewerId?: string;
  reviewerName?: string;
  reconRunId?: string | null;
  validation?: { result: string };
}> {
  return request(`/drafts/${encodeURIComponent(draftId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, comment, reviewer_id: reviewerId ?? "reviewer_demo" }),
  });
}

export async function listDraftVersions(draftId: string): Promise<DraftVersion[]> {
  return request(`/drafts/${encodeURIComponent(draftId)}/versions`);
}

export async function getNoticeAudit(noticeId: string): Promise<AuditEvent[]> {
  return request(`/notices/${encodeURIComponent(noticeId)}/audit`);
}

export function draftPdfUrl(draftId: string, version?: number): string {
  const v = version ? `?version=${version}` : "";
  return `${API_BASE_URL}/drafts/${encodeURIComponent(draftId)}/pdf${v}`;
}

export function coverLetterUrl(draftId: string, version?: number): string {
  const v = version ? `?version=${version}` : "";
  return `${API_BASE_URL}/drafts/${encodeURIComponent(draftId)}/cover-letter${v}`;
}

export type ContentChange = {
  kind: string;
  old?: string[];
  new?: string[];
  note?: string;
};

export type StructuredChange = {
  field: string;
  from?: unknown;
  to?: unknown;
  added?: string[];
  removed?: string[];
  changedKeys?: string[];
  changed: boolean;
  kind: string;
};

export type VersionCompare = {
  draftId: string;
  from: number;
  to: number;
  contentChanges: ContentChange[];
  structuredChanges: StructuredChange[];
  hasChanges: boolean;
};

export async function compareVersions(
  draftId: string,
  fromVersion: number,
  toVersion: number
): Promise<VersionCompare> {
  return request(
    `/drafts/${encodeURIComponent(draftId)}/compare?from_version=${fromVersion}&to_version=${toVersion}`
  );
}
