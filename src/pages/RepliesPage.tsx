import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/ui/PageHeader";
import { ReviewBanner } from "../components/ui/ReviewBanner";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { MetadataRow } from "../components/ui/MetadataRow";
import { StatusBadge } from "../components/ui/StatusBadge";
import { LoadingState, ErrorState } from "../components/ui/StateView";
import { CitationText } from "../components/agent/CitationText";
import { VersionHistory } from "../components/replies/VersionHistory";
import { VersionCompareView } from "../components/replies/VersionCompare";
import { ReviewerSwitcher } from "../components/replies/ReviewerSwitcher";
import { getNotice, listNotices } from "../services/notices";
import { getReconciliation } from "../services/reconciliation";
import {
  coverLetterUrl,
  draftPdfUrl,
  getReplyDraft,
  listReplyDrafts,
  runAgent,
  saveReplyDraft,
  submitReview,
} from "../services/agent";
import { loadActiveReviewerId } from "../services/reviewers";
import type { Notice, ReconciliationResult, ReplyDraft } from "../types";

function reviewTone(status?: string): "ok" | "warn" | "err" {
  if (status === "APPROVED") return "ok";
  if (status === "PENDING_REVIEW") return "warn";
  return "err";
}

export function RepliesPage() {
  const [params] = useSearchParams();
  const noticeId = params.get("noticeId") ?? "";

  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [draft, setDraft] = useState<ReplyDraft | null>(null);
  const [recon, setRecon] = useState<ReconciliationResult | null>(null);
  const [viewVersion, setViewVersion] = useState<number>(1);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    listNotices().then(setNotices).catch(() => setNotices([]));
  }, []);

  const load = useCallback(async () => {
    if (!noticeId) return;
    setLoading(true);
    setError(null);
    try {
      const [n, drafts] = await Promise.all([getNotice(noticeId), listReplyDrafts(noticeId)]);
      setNotice(n);
      const head = drafts[0] ?? null;
      setDraft(head);
      setViewVersion(head?.currentVersion ?? 1);
      setEditText(head?.content ?? "");
      try {
        setRecon(await getReconciliation(noticeId));
      } catch {
        setRecon(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load reply draft.");
    } finally {
      setLoading(false);
    }
  }, [noticeId]);

  useEffect(() => {
    setDraft(null);
    setNotice(null);
    void load();
  }, [load]);

  const refreshDraft = async (id: string) => {
    const updated = await getReplyDraft(id);
    setDraft(updated);
    setViewVersion(updated.currentVersion ?? 1);
    setEditText(updated.content ?? "");
  };

  const onSave = async () => {
    if (!draft) return;
    setBusy(true);
    setError(null);
    setFlash(null);
    try {
      // Saving an edit creates a NEW version; history is never overwritten.
      const updated = await saveReplyDraft(draft.id, { content: editText });
      setDraft(updated);
      setViewVersion(updated.currentVersion ?? 1);
      setEditing(false);
      setFlash(`Saved as v${updated.currentVersion}. Still requires human review.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  };

  const onReview = async (action: "APPROVE" | "REQUEST_CHANGES" | "REJECT") => {
    if (!draft) return;
    setBusy(true);
    setError(null);
    setFlash(null);
    try {
      await submitReview(draft.id, action, comment, loadActiveReviewerId());
      setComment("");
      await refreshDraft(draft.id);
      setFlash(
        action === "APPROVE"
          ? "Approved. Nothing is submitted externally."
          : action === "REQUEST_CHANGES"
            ? "Changes requested and recorded in the audit trail."
            : "Rejected and recorded in the audit trail."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review action failed.");
    } finally {
      setBusy(false);
    }
  };

  const onRegenerate = async () => {
    if (!noticeId) return;
    setBusy(true);
    setError(null);
    try {
      const run = await runAgent(noticeId);
      if (run.draftId) await refreshDraft(run.draftId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Regeneration failed.");
    } finally {
      setBusy(false);
    }
  };

  const versions = draft?.versions ?? [];
  const shownVersion = versions.find((v) => v.version === viewVersion) ?? null;
  const isCurrent = shownVersion?.version === draft?.currentVersion;
  const terminal = shownVersion && ["APPROVED", "REJECTED"].includes(shownVersion.reviewStatus);

  return (
    <>
      <PageHeader
        crumb="Workspace / Replies"
        title="Review draft"
        subtitle="Review-only. NoticePilot does not submit responses to the GST portal."
        actions={
          <>
            <button type="button" className="btn" disabled={!draft || busy} onClick={onSave}>
              Save draft
            </button>
            <button type="button" className="btn t" disabled={!noticeId || busy} onClick={() => void onRegenerate()}>
              {busy ? "Working…" : "Regenerate"}
            </button>
          </>
        }
      />
      <ReviewBanner />
      {!noticeId ? (
        <Card title="Select a notice">
          <div className="cb">
            {notices === null ? (
              <LoadingState label="Loading notices" />
            ) : (
              <ul>
                {(notices ?? []).map((n) => (
                  <li key={n.id}>
                    <Link to={`/replies?noticeId=${encodeURIComponent(n.id)}`}>
                      <span className="mono">{n.noticeNumber ?? n.id}</span> · {n.noticeType ?? "UNKNOWN"}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      ) : loading ? (
        <LoadingState label="Loading draft" />
      ) : error ? (
        <ErrorState message={error} />
      ) : !draft ? (
        <Card title="Review draft">
          <EmptyState
            title="No response draft"
            description="Run the agent review from the notice workspace to prepare a draft."
            action={
              <Link className="btn" to={`/notices/${noticeId}`}>
                Go to notice
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <section className="card">
            <div className="ch">
              <span className="h2s">Review draft [Draft v{draft.currentVersion}]</span>
              <StatusBadge label={draft.reviewStatus ?? "–"} tone={reviewTone(draft.reviewStatus)} />
              <StatusBadge label="Review required before submission" tone="err" />
            </div>
          </section>

          <div className="grid g2" style={{ marginTop: 16 }}>
            <div className="grid" style={{ alignContent: "start" }}>
              <Card title="Notice">
                <div className="cb">
                  <MetadataRow label="Notice number" value={notice?.noticeNumber} />
                  <MetadataRow label="Type" value={notice?.noticeType} />
                  <MetadataRow label="Tax period" value={notice?.taxPeriod} />
                </div>
              </Card>
              <Card title="Reconciliation">
                <div className="cb">
                  <MetadataRow label="Notice difference" value={recon?.noticeDifference?.toString()} />
                  <MetadataRow label="Explained" value={recon?.explainedAmount?.toString()} />
                  <MetadataRow label="Unexplained" value={recon?.unexplainedAmount?.toString()} />
                  <MetadataRow label="Status" value={recon?.status} />
                </div>
              </Card>
              <Card title="Citations">
                <div className="cb">
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {(draft.findingIds ?? []).map((id) => (
                      <li key={id}>
                        <Link
                          className="mono"
                          to={`/reconciliation?noticeId=${encodeURIComponent(noticeId)}&finding=${encodeURIComponent(id)}`}
                        >
                          [Finding {id}]
                        </Link>
                      </li>
                    ))}
                    {(draft.evidenceIds ?? []).map((id) => (
                      <li key={id}>
                        <Link className="mono" to={`/evidence?noticeId=${encodeURIComponent(noticeId)}`}>
                          [Evidence {id}]
                        </Link>
                      </li>
                    ))}
                    <li>
                      <span className="mono">[Rule {draft.ruleVersion?.includes("88C") ? "88C" : draft.ruleVersion?.includes("88D") ? "88D" : "–"} / {draft.ruleVersion ?? "–"}]</span>
                    </li>
                  </ul>
                </div>
              </Card>
              <VersionHistory
                versions={versions}
                noticeId={noticeId}
                selected={viewVersion}
                onSelect={setViewVersion}
              />
              <VersionCompareView draftId={draft.id} versions={versions} />
            </div>

            <div className="grid" style={{ alignContent: "start" }}>
              <section className="card">
                <div className="ch">
                  <span className="h2s">Response {isCurrent ? "(current)" : `(viewing v${viewVersion} — immutable)`}</span>
                </div>
                <div className="cb">
                  {editing ? (
                    <>
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        rows={24}
                        style={{ width: "100%", fontFamily: "inherit" }}
                        aria-label="Edit reply draft"
                      />
                      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                        <button type="button" className="btn t" disabled={busy} onClick={() => void onSave()}>
                          Save as new version
                        </button>
                        <button
                          type="button"
                          className="btn"
                          onClick={() => {
                            setEditText(draft.content ?? "");
                            setEditing(false);
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                      <p className="sub">Saving creates v{(draft.currentVersion ?? 1) + 1}; history is preserved.</p>
                    </>
                  ) : (
                    <>
                      <div style={{ whiteSpace: "pre-wrap" }}>
                        <CitationText text={shownVersion?.content ?? draft.content ?? ""} noticeId={noticeId} />
                      </div>
                      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                        <button type="button" className="btn" onClick={() => setEditing(true)}>
                          Edit text
                        </button>
                      </div>
                    </>
                  )}
                  {terminal ? (
                    <p className="sub">
                      v{shownVersion?.version} is {shownVersion?.reviewStatus} and immutable. Edit to create a new
                      pending version.
                    </p>
                  ) : null}
                </div>
              </section>

              <Card title="Review">
                <div className="cb">
                  <ReviewerSwitcher compact />
                  {draft.reviewStatus === "APPROVED" && draft.review ? (
                    <div style={{ marginTop: 8 }}>
                      <b>APPROVED</b>
                      <div className="cb" style={{ padding: 0 }}>
                        <MetadataRow label="Reviewed by" value={draft.review.reviewerName || draft.review.reviewerId} />
                        <MetadataRow label="Approved" value={draft.review.updatedAt ?? undefined} />
                        <MetadataRow label="Version" value={`v${draft.review.version ?? draft.currentVersion ?? "–"}`} />
                        <MetadataRow label="Validation" value={draft.review.validation?.result ?? "–"} />
                      </div>
                      <p className="sub">
                        Approval is immutable. Further edits create a new pending version; nothing is submitted
                        externally.
                      </p>
                    </div>
                  ) : null}
                  {draft.review?.comment ? (
                    <p className="sub" style={{ marginTop: 0 }}>
                      Latest reviewer comment: “{draft.review.comment}”
                    </p>
                  ) : null}
                  <label htmlFor="review-comment" className="sub">
                    Comment {`(required for changes / rejection)`}
                  </label>
                  <textarea
                    id="review-comment"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={3}
                    style={{ width: "100%", fontFamily: "inherit" }}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                    <button type="button" className="btn" disabled={busy} onClick={() => void onReview("REQUEST_CHANGES")}>
                      Request changes
                    </button>
                    <button type="button" className="btn" disabled={busy} onClick={() => void onReview("REJECT")}>
                      Reject
                    </button>
                    <button type="button" className="btn t" disabled={busy} onClick={() => void onReview("APPROVE")}>
                      Approve
                    </button>
                  </div>
                  <p className="sub">Approval is server-validated against evidence, citations and reconciliation.</p>
                </div>
              </Card>

              <Card title="Export">
                <div className="cb">
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <a className="btn" href={draftPdfUrl(draft.id)} target="_blank" rel="noreferrer">
                      Download PDF
                    </a>
                    <a className="btn" href={coverLetterUrl(draft.id)} target="_blank" rel="noreferrer">
                      Cover letter
                    </a>
                  </div>
                  <p className="sub">The PDF is stamped “REVIEW DRAFT — NOT FILED”. The cover letter is a
                  human-carried document, never a filing.</p>
                </div>
              </Card>
            </div>
          </div>
          {flash ? <p className="sub">{flash}</p> : null}
        </>
      )}
    </>
  );
}
