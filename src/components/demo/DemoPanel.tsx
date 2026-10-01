import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/StateView";
import {
  DEMO_LABEL,
  isDemoMode,
  resetDemo,
  supplementDemo,
  type DemoResetResult,
  type DemoSupplementResult,
} from "../../services/demo";
import { getReplyDraft, listReplyDrafts, runAgent } from "../../services/agent";
import { runReconciliation } from "../../services/reconciliation";

type DemoState = DemoResetResult | DemoSupplementResult | null;

export function DemoPanel({ onNotice }: { onNotice?: (noticeId: string) => void }) {
  const navigate = useNavigate();
  const [state, setState] = useState<DemoState>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isDemoMode()) return null;

  const run = async (label: string, fn: () => Promise<Exclude<DemoState, null>>) => {
    setBusy(label);
    setError(null);
    try {
      const result = await fn();
      setState(result);
      onNotice?.(result.noticeId);
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed.`);
    } finally {
      setBusy(null);
    }
  };

  const noticeId = state?.noticeId ?? "";

  const openLatestDraft = async () => {
    if (!noticeId) return;
    setBusy("draft");
    setError(null);
    try {
      const drafts = await listReplyDrafts(noticeId);
      if (drafts.length > 0) {
        navigate(`/replies?noticeId=${encodeURIComponent(noticeId)}`);
      } else {
        const agentRun = await runAgent(noticeId);
        if (agentRun.draftId) await getReplyDraft(agentRun.draftId);
        navigate(`/replies?noticeId=${encodeURIComponent(noticeId)}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open draft.");
    } finally {
      setBusy(null);
    }
  };

  const rerunRecon = async () => {
    if (!noticeId) return;
    setBusy("recon");
    setError(null);
    try {
      const recon = await runReconciliation(noticeId);
      setState((prev) =>
        prev
          ? {
              ...prev,
              reconciliation: {
                status: recon.status ?? "",
                noticeDifference: recon.noticeDifference ?? 0,
                explainedAmount: recon.explainedAmount ?? 0,
                unexplainedAmount: recon.unexplainedAmount ?? 0,
              },
            }
          : prev
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reconciliation failed.");
    } finally {
      setBusy(null);
    }
  };

  const regenAgent = async () => {
    if (!noticeId) return;
    setBusy("agent");
    setError(null);
    try {
      const agentRun = await runAgent(noticeId);
      setState((prev) =>
        prev
          ? { ...prev, agentRun: { id: agentRun.id, status: agentRun.status, decision: agentRun.decision ?? "" } }
          : prev
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent run failed.");
    } finally {
      setBusy(null);
    }
  };

  const busyLabel = (label: string) => (busy === label ? "Working…" : null);

  return (
    <Card title="Synthetic demo controls">
      <div className="cb">
        <p className="sub" style={{ marginTop: 0 }}>
          {DEMO_LABEL} Demo controls are visible because demo/dev mode is on.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="btn t" disabled={busy !== null} onClick={() => void run("reset", resetDemo)}>
            {busyLabel("reset") ?? "Reset synthetic demo"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={busy !== null || !noticeId}
            onClick={() => noticeId && void run("supplement", () => supplementDemo(noticeId))}
          >
            {busyLabel("supplement") ?? "Upload supplemental evidence"}
          </button>
          <button type="button" className="btn" disabled={busy !== null || !noticeId} onClick={() => void rerunRecon()}>
            {busyLabel("recon") ?? "Rerun reconciliation"}
          </button>
          <button type="button" className="btn" disabled={busy !== null || !noticeId} onClick={() => void regenAgent()}>
            {busyLabel("agent") ?? "Generate / re-run agent review"}
          </button>
          <button type="button" className="btn" disabled={busy !== null || !noticeId} onClick={() => void openLatestDraft()}>
            {busyLabel("draft") ?? "Open latest draft"}
          </button>
          {noticeId ? (
            <>
              <Link className="btn" to={`/notices/${encodeURIComponent(noticeId)}`}>
                Open notice &amp; audit
              </Link>
              <Link className="btn" to={`/replies?noticeId=${encodeURIComponent(noticeId)}`}>
                Export PDF
              </Link>
            </>
          ) : null}
        </div>
        {busy && !["reset", "supplement", "recon", "agent", "draft"].includes(busy) ? (
          <LoadingState label="Working" />
        ) : null}
        {error ? (
          <p role="alert" style={{ color: "var(--err, #b3261e)" }}>
            {error}
          </p>
        ) : null}
        {state ? (
          <div className="mono sub" style={{ marginTop: 8 }}>
            Stage: {state.stage} · Recon {state.reconciliation.status} (
            {state.reconciliation.explainedAmount}/{state.reconciliation.unexplainedAmount} unexplained) ·
            Agent {state.agentRun.decision}
            {noticeId ? (
              <>
                {" · "}
                <Link to={`/notices/${encodeURIComponent(noticeId)}`}>Open notice</Link>
              </>
            ) : null}
          </div>
        ) : (
          <EmptyState
            title="No demo state yet"
            description="Reset the synthetic demo to walk the full workflow from real application state."
          />
        )}
      </div>
    </Card>
  );
}
