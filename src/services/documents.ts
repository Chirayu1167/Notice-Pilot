import type { DocumentUploadResponse, ExtractionResponse } from "../types";
import { API_BASE_URL, request } from "./api";

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentUploadResponse>("/documents/upload", {
    method: "POST",
    body: form,
  });
}

export async function extractDocument(documentId: string): Promise<ExtractionResponse> {
  return request<ExtractionResponse>(`/documents/${encodeURIComponent(documentId)}/extract`, {
    method: "POST",
  });
}

export function downloadDocumentUrl(documentId: string): string {
  return `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/download`;
}

export async function getDocumentText(
  documentId: string
): Promise<{ documentId: string; status: string; text: string }> {
  return request(`/documents/${encodeURIComponent(documentId)}/text`);
}
