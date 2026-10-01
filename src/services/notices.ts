import type { Notice } from "../types";
import { request } from "./api";

export async function parseNotice(documentId: string): Promise<Notice> {
  return request<Notice>(`/notices/parse/${encodeURIComponent(documentId)}`, {
    method: "POST",
  });
}

export async function listNotices(): Promise<Notice[]> {
  return request<Notice[]>("/notices/");
}

export async function getNotice(id: string): Promise<Notice> {
  return request<Notice>(`/notices/${encodeURIComponent(id)}`);
}
