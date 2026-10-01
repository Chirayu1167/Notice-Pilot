import type { FindingLineage, ReconciliationResult, ReturnData, ReturnRow } from "../types";
import { API_BASE_URL, request } from "./api";

export async function getReconciliation(noticeId: string): Promise<ReconciliationResult> {
  return request<ReconciliationResult>(`/notices/${encodeURIComponent(noticeId)}/reconciliation`);
}

export async function runReconciliation(noticeId: string): Promise<ReconciliationResult> {
  return request<ReconciliationResult>(`/notices/${encodeURIComponent(noticeId)}/reconciliation`, {
    method: "POST",
  });
}

export async function getReconciliationRun(runId: string): Promise<ReconciliationResult> {
  return request<ReconciliationResult>(`/reconciliation/${encodeURIComponent(runId)}`);
}

export async function listReturnData(noticeId: string): Promise<ReturnData[]> {
  return request<ReturnData[]>(`/notices/${encodeURIComponent(noticeId)}/return-data`);
}

export async function getReturnRows(noticeId: string, rowIds: string[]): Promise<ReturnRow[]> {
  const ids = rowIds.map((id) => encodeURIComponent(id)).join(",");
  return request<ReturnRow[]>(
    `/notices/${encodeURIComponent(noticeId)}/return-rows?ids=${ids}`
  );
}

export async function getFindingLineage(findingId: string): Promise<FindingLineage> {
  return request<FindingLineage>(`/reconciliation/findings/${encodeURIComponent(findingId)}/lineage`);
}

export function downloadReturnFileUrl(downloadUrl: string): string {
  return `${API_BASE_URL}${downloadUrl}`;
}

export function downloadNoticeFileUrl(documentId: string): string {
  return `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/download`;
}

export async function uploadReturnData(
  noticeId: string,
  file: File,
  opts?: { source?: string; period?: string }
): Promise<ReturnData> {
  const form = new FormData();
  form.append("file", file);
  if (opts?.source && opts.source !== "AUTO") form.append("source", opts.source);
  if (opts?.period) form.append("period", opts.period);
  const res = await fetch(
    `${API_BASE_URL}/notices/${encodeURIComponent(noticeId)}/return-data`,
    { method: "POST", body: form }
  );
  if (!res.ok) {
    let message = `Upload failed (${res.status}).`;
    try {
      const data = await res.json();
      const detail = data?.detail;
      if (typeof detail === "string") message = detail;
      else if (detail && typeof detail.message === "string") message = detail.message;
    } catch {
      // keep generic message
    }
    throw new Error(message);
  }
  return (await res.json()) as ReturnData;
}

export function requiredSources(noticeType?: string | null): string[] {
  if (noticeType === "DRC-01B") return ["GSTR-1", "GSTR-3B"];
  if (noticeType === "DRC-01C") return ["GSTR-2B", "GSTR-3B"];
  return [];
}

export function missingSources(noticeType: string | undefined, returns: ReturnData[]): string[] {
  const required = requiredSources(noticeType);
  const present = new Set((returns ?? []).map((r) => r.source));
  return required.filter((s) => !present.has(s));
}
