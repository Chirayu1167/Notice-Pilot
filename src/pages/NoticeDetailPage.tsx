import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../components/ui/PageHeader";
import { ReviewBanner } from "../components/ui/ReviewBanner";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { DeadlineBadge, deadlineInfo } from "../components/ui/DeadlineBadge";
import { MetadataRow } from "../components/ui/MetadataRow";
import { LoadingState, ErrorState } from "../components/ui/StateView";
import { DocumentPreview } from "../components/DocumentPreview";
import { INGEST_STAGES, Timeline, type TimelineStageState } from "../components/Timeline";
import { noticeStatusTone } from "../components/notices/noticeStatus";
import { formatAmount } from "../components/notices/NoticeTable";
import { getNotice } from "../services/notices";
import { downloadDocumentUrl, getDocumentText } from "../services/documents";
import { ReturnDataSection } from "../components/reconciliation/ReturnDataSection";
import { AgentReviewSection } from "../components/agent/AgentReviewSection";
import { AuditTimeline } from "../components/replies/AuditTimeline";
import type { Notice } from "../types";

function formatSize(bytes?: number | null): string | undefined {
  if (bytes === undefined || bytes === null) return undefined;
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export function NoticeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [notice, setNotice] = useState<Notice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [extractedText, setExtractedText] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getNotice(id)
      .then((data) => {
        if (cancelled) return;
        setNotice(data);
        if (data.documentId && data.mimeType === "text/plain") {
          getDocumentText(data.documentId)
            .then((res) => {
              if (!cancelled) setExtractedText(res.text);
            })
            .catch(() => {
              // preview stays honest: no text available
            });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load notice.");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <>
        <PageHeader crumb="Notices / Detail" title="Notice details" />
        <ErrorState message={error} />
        <p>
          <Link to="/notices">Back to notices</Link>
        </p>
      </>
    );
  }

  if (!notice) {
    return (
      <>
        <PageHeader crumb="Notices / Detail" title="Notice details" />
        <LoadingState label="Loading notice" />
      </>
    );
  }

  const stageStates: TimelineStageState[] = INGEST_STAGES.map(() => "done");
  const notes = INGEST_STAGES.map((name) =>
    name === "Completed" ? `${notice.status ?? "Processed"}` : "Complete"
  );

  const isPdf = notice.mimeType === "application/pdf";

  return (
    <>
      <PageHeader
        crumb="Notices / Detail"
        title={notice.noticeNumber ?? "Notice details"}
        subtitle={
          notice.noticeType && notice.noticeType !== "UNKNOWN" ? (
            <>
              <span className="mono">{notice.noticeType}</span>
              {notice.taxPeriod ? (
                <>
                  {" "}· <span className="mono">Period: {notice.taxPeriod}</span>
                </>
              ) : null}
            </>
          ) : (
            "Notice details will appear after processing."
          )
        }
        actions={
          <>
            <StatusBadge label={notice.status ?? "–"} tone={noticeStatusTone(notice.status)} />
            <DeadlineBadge dueDate={notice.dueDate} />
          </>
        }
      />
      <ReviewBanner />
      <div className="grid g2">
        <div className="grid">
          <Card title="Notice header">
            <div className="cb">
              <MetadataRow label="Notice number" value={notice.noticeNumber} />
              <MetadataRow label="Notice type" value={notice.noticeType} />
              <MetadataRow label="GSTIN" value={notice.gstin} />
              <MetadataRow label="Tax period" value={notice.taxPeriod} />
              <MetadataRow label="Issue date" value={notice.issueDate} />
            </div>
          </Card>
          <Card title="Mismatch summary">
            <div className="cb">
              <MetadataRow label="Difference" value={formatAmount(notice.differenceAmount)} />
            </div>
          </Card>
          <Card title="Requested action">
            {notice.requestedAction ? (
              <div className="cb">
                <p style={{ margin: 0 }}>{notice.requestedAction}</p>
              </div>
            ) : (
              <EmptyState
                title="Not extracted"
                description="The action requested in the notice will appear after processing."
              />
            )}
          </Card>
          <ReturnDataSection notice={notice} />
          <AgentReviewSection notice={notice} />
        </div>
        <div className="grid">
          <Card title="Deadline">
            <div className="cb">
              <MetadataRow label="Issue date" value={notice.issueDate} />
              <MetadataRow label="Reply by" value={notice.dueDate} />
              <MetadataRow
                label="Time remaining"
                value={deadlineInfo(notice.dueDate).kind === "none" ? undefined : deadlineInfo(notice.dueDate).label}
              />
            </div>
          </Card>
          <Card title="Source document">
            <div className="cb">
              <MetadataRow label="Filename" value={notice.filename} />
              <MetadataRow label="Extraction" value={notice.extractionStatus} />
              <MetadataRow label="Size" value={formatSize(notice.documentSize)} />
              <div style={{ marginTop: 12 }}>
                <DocumentPreview
                  title={notice.filename ?? "Source document"}
                  text={extractedText ?? undefined}
                  pdfUrl={isPdf && notice.documentId ? downloadDocumentUrl(notice.documentId) : undefined}
                />
              </div>
            </div>
          </Card>
          <Card title="Processing status">
            <div className="cb">
              <Timeline stages={INGEST_STAGES} stageStates={stageStates} notes={notes} />
            </div>
          </Card>
          <AuditTimeline noticeId={notice.id} compact />
        </div>
      </div>
    </>
  );
}
