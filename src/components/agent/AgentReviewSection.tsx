import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { StatusBadge } from "../ui/StatusBadge";
import { LoadingState } from "../ui/StateView";
import { Timeline, type TimelineStageState } from "../Timeline";
import {
  getAgentRun,
  getAgentStatus,
  getNoticeAudit,
  getNoticeEvidence,
  listAgentRuns,
  replanAgent,
  runAgent,
  type AgentRun,
  type AgentStatus,
  type AuditEvent,
  type MissingEvidence,
  type NoticeEvidence,
} from "../../services/agent";
import { uploadReturnData } from "../../services/reconciliation";
import type { Notice } from "../../types";

const AGENT_STAGES = [
  "Notice analyzed",
  "Reconciliation checked",
  "Evidence reviewed",
  "Missing evidence identified",
  "Decision prepared",
] as const;

function decisionTone(decision?: string | null): "ok" | "warn" | "err" {
  if (decision === "CONTEST") return "ok";
  if (decision === "PARTIAL_ACCEPT") return "warn";
  return "err";
}

function decisionLabel(decision?: string | null): string {
  if (decision === "CONTEST") return "CONTEST";
  if (decision === "PARTIAL_ACCEPT") return "PARTIAL ACCEPT";
  return "INSUFFICIENT EVIDENCE";
}

function runStatusLabel(status: string): string {
  switch (status) {
    case "ANALYZING":
    case "INSPECTING_EVIDENCE":
    case "EVALUATING":
      return "Analyzing";
    case "WAITING_FOR_EVIDENCE":
      return "Waiting for evidence";
    case "READY_FOR_DRAFT":
    case "DRAFT_READY":
      return "Ready for review";
    case "HUMAN_REVIEW":
      return "In human review";
    case "ERROR":
      return "Agent error";
    default:
      return status;
  }
}

export function AgentReviewSection({ notice, onChanged }: { notice: Notice; onChanged?: () => void }) {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [active, setActive] = useState<AgentRun | null>(null);
  const [evidence, setEvidence] = useState<NoticeEvidence | null>(null);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = async () => {
    const [st, list, ev, au] = await Promise.all([
      getAgentStatus(),
      listAgentRuns(notice.id),
      getNoticeEvidence(notice.id).catch(() => null),
      getNoticeAudit(notice.id).catch(() => [] as AuditEvent[]),
    ]);
    setStatus(st);
    setRuns(list);
    setEvidence(ev);
    setAudit(au);
    if (list.length > 0 && !active) {
      const full = await getAgentRun(list[0].id);
      setActive(full);
    }
  };

  useEffect(() => {
    let cancelled = false;
    setRuns(null);
    setActive(null);
    refresh().catch((err: unknown) => {
      if (!cancelled) setError(err instanceof Error ? err.message : "Could not load agent state.");
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notice.id]);

  const doRun = async () => {
    setBusy(true);
    setError(null);
    try {
      const run = await runAgent(notice.id);
      setActive(run);
      setRuns(await listAgentRuns(notice.id));
      setEvidence(await getNoticeEvidence(notice.id).catch(() => null));
      setAudit(await getNoticeAudit(notice.id).catch(() => []));
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent run failed.");
    } finally {
      setBusy(false);
    }
  };

  const selectRun = async (runId: string) => {
    setBusy(true);
    setError(null);
    try {
      setActive(await getAgentRun(runId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load agent run.");
    } finally {
      setBusy(false);
    }
  };

  const doUploadMissing = async (file: File, source?: string | null, period?: string | null) => {
    setUploading(true);
    setError(null);
    try {
      // 1-3. validate, store, associate (existing return-data pipeline).
      await uploadReturnData(notice.id, file, {
        source: source ?? undefined,
        period: period ?? notice.taxPeriod ?? undefined,
      });
      // 4-6. rerun deterministic reconciliation, rebuild evidence, rerun agent.
      const { agentRun } = await replanAgent(notice.id);
      setActive(agentRun);
      setRuns(await listAgentRuns(notice.id));
      setEvidence(await getNoticeEvidence(notice.id).catch(() => null));
      setAudit(await getNoticeAudit(notice.id).catch(() => []));
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evidence upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const missing: MissingEvidence[] = evidence?.missing ?? [];
  const suggested = missing.find((m) => m.type === "RETURN_DOCUMENT");

  const stageStates: TimelineStageState[] = AGENT_STAGES.map((_, i) => {
    if (!active || active.status === "ERROR") return "waiting";
    const doneCount =
      active.status === "WAITING_FOR_EVIDENCE" || active.status === "DRAFT_READY" || active.status === "HUMAN_REVIEW"
        ? 5
        : 2;
    return i < doneCount ? "done" : "waiting";
  });

  return (
    <Card title="Agent review">
      <div className="cb">
        {status && !status.available ? (
          <p className="sub" style={{ marginTop: 0 }}>
            {status.message}
          </p>
        ) : null}

        {!runs ? (
          <LoadingState label="Loading agent state" />
        ) : !active ? (
          <EmptyState
            title="No agent review yet"
            description="The agent checks the notice, reconciliation and evidence, then prepares a review-only draft."
            action={
              <button type="button" className="btn t" disabled={busy} onClick={() => void doRun()}>
                {busy ? "Analyzing…" : "Run agent review"}
              </button>
            }
          />
        ) : (
          <>
            <p style={{ marginTop: 0 }}>
              <b>Status:</b> {runStatusLabel(active.status)}
              {active.status === "ERROR" && active.error ? (
                <span className="sub"> — {active.error} Deterministic reconciliation remains available.</span>
              ) : null}
            </p>
            {active.decision ? (
              <>
                <p>
                  <b>Decision:</b>{" "}
                  <StatusBadge label={decisionLabel(active.decision)} tone={decisionTone(active.decision)} />{" "}
                  {active.requiresHumanReview ? <StatusBadge label="Human review required" tone="warn" /> : null}
                </p>
                {active.reasoningSummary ? (
                  <p>
                    <b>Why:</b> {active.reasoningSummary}
                  </p>
                ) : null}
              </>
            ) : null}
            {evidence ? (
              <p>
                <b>Evidence:</b> {evidence.verified.length} verified · {evidence.partial.length} partial ·{" "}
                {evidence.missing.length} missing
              </p>
            ) : null}

            <Timeline stages={AGENT_STAGES} stageStates={stageStates} notes={AGENT_STAGES.map(() => "")} />
            {runs && runs.length > 1 ? (
              <div style={{ marginTop: 8 }}>
                <b>Agent runs</b>
                <ul style={{ margin: "4px 0", paddingLeft: 18 }}>
                  {runs.map((r, i) => {
                    const replan = i > 0 && (audit ?? []).some(
                      (e) =>
                        (e.action === "RETURN_UPLOADED" || e.action === "DEMO_RESET") &&
                        (e.createdAt ?? "") > (runs[i - 1].createdAt ?? "")
                    );
                    return (
                      <li key={r.id} className={r.id === active?.id ? "" : "sub"}>
                        <button
                          type="button"
                          className="btn"
                          style={{ padding: "2px 8px", fontSize: 12 }}
                          onClick={() => void selectRun(r.id)}
                        >
                          Run {runs.length - i}
                        </button>{" "}
                        <span className="mono">{r.decision ?? r.status}</span>{" "}
                        <span className="sub">{r.createdAt ?? ""}</span>{" "}
                        {replan ? (
                          <StatusBadge label="RE-PLAN TRIGGERED — new evidence uploaded" tone="warn" />
                        ) : null}
                        {r.id === active?.id ? <span className="sub"> (showing)</span> : null}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}
            {active.steps && active.steps.length > 0 ? (
              <div style={{ marginTop: 8 }}>
                <b>Agent run — tool trace</b>
                <div className="tw">
                  <table aria-label="Agent tool trace">
                    <thead>
                      <tr>
                        <th scope="col">#</th>
                        <th scope="col">Tool</th>
                        <th scope="col">Result</th>
                        <th scope="col">Status</th>
                        <th scope="col">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {active.steps.map((step) => (
                        <tr key={step.sequence}>
                          <td className="mono">{step.sequence}</td>
                          <td>
                            <button
                              type="button"
                              className="btn mono"
                              style={{ padding: "2px 8px", fontSize: 12 }}
                              onClick={() => setExpandedStep(expandedStep === step.sequence ? null : step.sequence)}
                              aria-expanded={expandedStep === step.sequence}
                              title={step.purpose}
                            >
                              {step.tool}
                            </button>
                            {expandedStep === step.sequence ? (
                              <div className="sub" style={{ marginTop: 4 }}>
                                Purpose: {step.purpose}
                              </div>
                            ) : null}
                          </td>
                          <td className="sub">{step.resultSummary}</td>
                          <td>
                            <StatusBadge label={step.status} tone={step.status === "ok" ? "ok" : "err"} />
                          </td>
                          <td className="mono sub">{step.createdAt ?? "–"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="sub">Structured tool summaries only — no hidden reasoning is shown.</p>
              </div>
            ) : null}

            {missing.length > 0 ? (
              <div style={{ marginTop: 12 }}>
                <b>Missing evidence</b>
                <ul style={{ margin: "4px 0", paddingLeft: 18 }}>
                  {missing.map((m, i) => (
                    <li key={i} className="sub">
                      {m.source ? <span className="mono">{m.source}</span> : m.type}
                      {m.amount ? ` — ₹${Number(m.amount).toLocaleString("en-IN")}` : ""}: {m.reason}
                    </li>
                  ))}
                </ul>
                <label className="btn" aria-disabled={uploading}>
                  {uploading ? "Uploading…" : "Upload missing evidence (CSV/XLSX)"}
                  <input
                    type="file"
                    accept=".csv,.xlsx"
                    hidden
                    disabled={uploading}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (file) void doUploadMissing(file, suggested?.source, suggested?.period);
                    }}
                  />
                </label>
                {suggested ? (
                  <span className="sub" style={{ marginLeft: 8 }}>
                    Suggested: <span className="mono">{suggested.source}</span> for {suggested.period ?? "notice period"}
                  </span>
                ) : null}
              </div>
            ) : null}

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
              <Link className="btn" to={`/evidence?noticeId=${encodeURIComponent(notice.id)}`}>
                View evidence
              </Link>
              <button type="button" className="btn" disabled={busy} onClick={() => void doRun()}>
                {busy ? "Running…" : "Run again"}
              </button>
              {active.draftId ? (
                <Link className="btn t" to={`/replies?noticeId=${encodeURIComponent(notice.id)}`}>
                  Review draft
                </Link>
              ) : null}
            </div>
          </>
        )}

        {error ? (
          <p role="alert" style={{ color: "var(--err, #b3261e)" }}>
            {error}
          </p>
        ) : null}
      </div>
    </Card>
  );
}
