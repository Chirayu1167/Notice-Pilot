import type { EvidenceItem } from "../types";
import { request } from "./api";

export async function listEvidence(findingId?: string): Promise<EvidenceItem[]> {
  const query = findingId ? `?findingId=${encodeURIComponent(findingId)}` : "";
  return request<EvidenceItem[]>(`/evidence${query}`);
}
