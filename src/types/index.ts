export type NoticeStatus =
  | "PROCESSING"
  | "VALID"
  | "PARTIAL"
  | "UNSUPPORTED"
  | "ERROR";

export type DocumentStatus =
  | "UPLOADED"
  | "EXTRACTING"
  | "EXTRACTED"
  | "FAILED";

export type NoticeType = "DRC-01B" | "DRC-01C" | "UNKNOWN";

export type DocumentInfo = {
  id: string;
  filename?: string;
  mimeType?: string;
  size?: number;
  extractionStatus?: DocumentStatus | string;
};

export type Notice = {
  id: string;
  documentId?: string;
  type?: string;
  noticeType?: NoticeType | string;
  gstin?: string;
  taxPeriod?: string;
  noticeNumber?: string;
  issueDate?: string;
  dueDate?: string;
  differenceAmount?: number;
  requestedAction?: string;
  status?: NoticeStatus | string;
  sourceDocumentId?: string;
  filename?: string;
  mimeType?: string;
  documentSize?: number;
  extractionStatus?: DocumentStatus | string;
  document?: DocumentInfo;
};

export type ReturnRow = {
  id: string;
  returnId?: string;
  source?: string;
  period?: string;
  supplierGstin?: string | null;
  recipientGstin?: string | null;
  invoiceNumber?: string | null;
  date?: string;
  invoiceDate?: string | null;
  description?: string;
  amount?: number;
  taxableValue?: number | null;
  igst?: number | null;
  cgst?: number | null;
  sgst?: number | null;
  cess?: number | null;
  totalTax?: number | null;
  creditDebitNote?: string | null;
  raw?: Record<string, unknown>;
};

export type ReturnData = {
  id: string;
  noticeId?: string;
  source?: string;
  taxPeriod?: string;
  period?: string;
  periodStatus?: "MATCH" | "MISMATCH" | "UNKNOWN" | string;
  filename?: string;
  rowCount?: number;
  status?: string;
  originalFileStored?: boolean;
  downloadUrl?: string;
  rows?: ReturnRow[];
};

export type FindingCalculation = {
  rule?: string | null;
  formula?: string | null;
  inputs?: Record<string, unknown>;
  ruleVersion?: string;
};

export type FindingStatus =
  | "MATCHED"
  | "MISMATCH"
  | "MISSING_DATA"
  | "PERIOD_MISMATCH"
  | "UNSUPPORTED"
  | "matched"
  | "mismatch"
  | "needs_evidence";

export type Finding = {
  id: string;
  reconciliationId?: string;
  metric?: string;
  category?: string;
  description?: string;
  amount?: number | null;
  sourceRows?: string[];
  calculation?: FindingCalculation;
  sourceA?: number;
  sourceB?: number;
  difference?: number;
  status?: FindingStatus | string;
};

export type ReconciliationStatus =
  | "MATCHED"
  | "PARTIAL"
  | "UNEXPLAINED"
  | "MISSING_DATA"
  | "UNSUPPORTED";

export type ReconciliationResult = {
  id: string;
  noticeId?: string;
  taxPeriod?: string;
  status?: ReconciliationStatus | string;
  noticeDifference?: number;
  calculatedDifference?: number;
  explainedAmount?: number;
  unexplainedAmount?: number;
  ruleVersion?: string;
  totalA?: number;
  totalB?: number;
  netVariance?: number;
  findings?: Finding[];
};

export type EvidenceStatus = "attached" | "unlinked" | "pending";

export type FindingLineage = {
  finding: Finding & { runId?: string };
  calculation: FindingCalculation;
  notice: Notice;
  noticeDocument?: { id: string; filename?: string; mimeType?: string; downloadUrl?: string };
  run?: ReconciliationResult;
  returnRows: ReturnRow[];
  returnDocuments: ReturnData[];
  chain: string[];
};

export type EvidenceItem = {
  id: string;
  documentId?: string;
  findingId?: string;
  source?: string;
  status?: EvidenceStatus;
};

export type ReplyDraft = {
  id: string;
  noticeId?: string;
  agentRunId?: string | null;
  decision?: string | null;
  content?: string;
  evidenceIds?: string[];
  findingIds?: string[];
  ruleVersion?: string | null;
  status?: "draft" | "in_review" | "ready" | string;
  requiresReview?: boolean;
  currentVersion?: number;
  reviewStatus?: ReviewStatus | string;
  review?: DraftReview | null;
  versions?: DraftVersion[];
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type ReviewStatus =
  | "PENDING_REVIEW"
  | "CHANGES_REQUESTED"
  | "APPROVED"
  | "REJECTED";

export type DraftVersion = {
  id: string;
  draftId: string;
  version: number;
  content: string;
  decision?: string | null;
  findingIds: string[];
  evidenceIds: string[];
  ruleVersion?: string | null;
  reconSnapshot?: Record<string, unknown>;
  createdBy: string;
  agentRunId?: string | null;
  parentVersionId?: string | null;
  reviewStatus: ReviewStatus | string;
  createdAt?: string | null;
};

export type DraftReview = {
  status: ReviewStatus | string;
  comment?: string;
  reviewerId?: string;
  reviewerName?: string;
  reconRunId?: string | null;
  validation?: { result?: string; ruleVersion?: string; reconRunId?: string; reconStatus?: string };
  version?: number;
  updatedAt?: string | null;
};

export type AuditEvent = {
  id: string;
  noticeId: string;
  actorType: "SYSTEM" | "AGENT" | "REVIEWER" | string;
  actorId?: string;
  action: string;
  entityType?: string;
  entityId?: string;
  metadata?: Record<string, unknown>;
  createdAt?: string | null;
};

export type Document = {
  id: string;
  name?: string;
  filename?: string;
  mimeType?: string;
  size?: number;
  uploadedAt?: string;
  extractionStatus?: DocumentStatus | string;
  pageCount?: number;
};

export type DocumentUploadResponse = {
  document: DocumentInfo;
  status: string;
};

export type ExtractionResponse = {
  documentId: string;
  status: string;
  text?: string;
  pageCount?: number;
  message?: string;
};

export type UploadResult = {
  received: boolean;
  fileName: string;
  message: string;
};
