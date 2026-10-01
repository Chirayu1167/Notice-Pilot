import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/ui/PageHeader";
import { ReviewBanner } from "../components/ui/ReviewBanner";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { LoadingState, ErrorState } from "../components/ui/StateView";
import { ReconciliationTable, findingTone, formatINR } from "../components/reconciliation/ReconciliationTable";
import { FindingLineageCard } from "../components/reconciliation/FindingLineage";
import { getNotice, listNotices } from "../services/notices";
import {
  getFindingLineage,
  getReconciliation,
  listReturnData,
  missingSources,
  runReconciliation,
} from "../services/reconciliation";
import type { Finding, FindingLineage, Notice, ReconciliationResult, ReturnData } from "../types";

export function ReconciliationPage() {
  const [params] = useSearchParams();
  const noticeId = params.get("noticeId") ?? "";
  const findingParam = params.get("finding") ?? "";

  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [returns, setReturns] = useState<ReturnData[]>([]);
  const [result, setResult] = useState<ReconciliationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [lineage, setLineage] = useState<FindingLineage | null>(null);
  const [lineageLoading, setLineageLoading] = useState(false);
  const [lineageError, setLineageError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listNotices()
      .then((data) => {
        if (!cancelled) setNotices(data);
      })
      .catch(() => {
        if (!cancelled) setNotices([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!noticeId) {
      setNotice(null);
      setResult(null);
      setReturns([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      const n = await getNotice(noticeId);
      if (cancelled) return;
      setNotice(n);
      setReturns(await listReturnData(noticeId));
      try {
        setResult(await getReconciliation(noticeId));
      } catch {
        if (!cancelled) setResult(null);
      }
    })()
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load reconciliation.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [noticeId]);

  const missing = useMemo(
    () => missingSources(notice?.noticeType, returns),
    [notice, returns]
  );

  const onRun = async () => {
    if (!noticeId) return;
    setRunning(true);
    setError(null);
    try {
      setResult(await runReconciliation(noticeId));
      setSelectedFinding(null);
      setLineage(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reconciliation failed.");
    } finally {
      setRunning(false);
    }
  };

  const onSelectFinding = (finding: Finding) => {
    setSelectedFinding(finding);
    setLineage(null);
    setLineageError(null);
    setLineageLoading(true);
    getFindingLineage(finding.id)
      .then((data) => setLineage(data))
      .catch((err: unknown) => {
        setLineageError(err instanceof Error ? err.message : "Could not load evidence chain.");
      })
      .finally(() => setLineageLoading(false));
  };

  // Deep link from draft citations: ?finding=<findingId> opens its lineage.
  useEffect(() => {
    if (!findingParam || !result?.findings) return;
    const match = result.findings.find((f) => f.id === findingParam);
    if (match && match.id !== selectedFinding?.id) onSelectFinding(match);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findingParam, result]);

  const subtitle = notice ? (
    <>
      <span className="mono">Notice ref: {notice.noticeNumber ?? notice.id}</span> &nbsp;{" "}
      <span className="mono">Period: {notice.taxPeriod ?? "–"}</span> &nbsp;{" "}
      <span className="mono">Total mismatch: {formatINR(notice.differenceAmount)}</span>
    </>
  ) : (
    <>
      <span className="mono">Notice ref: –</span> &nbsp; <span className="mono">Period: –</span> &nbsp;{" "}
      <span className="mono">Total mismatch: –</span>
    </>
  );

  return (
    <>
      <PageHeader
        crumb="Workspace / Reconciliation"
        title="Reconciliation"
        subtitle={subtitle}
        actions={
          <>
            {notice ? (
              <Link className="btn" to={`/notices/${notice.id}`}>
                Back to notice
              </Link>
            ) : null}
            <button type="button" className="btn t" disabled={!noticeId || missing.length > 0 || running} onClick={() => void onRun()}>
              {running ? "Running…" : "Re-run rules check"}
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
            ) : notices.length === 0 ? (
              <EmptyState
                title="No notices yet"
                description="Upload a GST notice first, then open reconciliation from the notice workspace."
              />
            ) : (
              <ul>
                {notices.map((n) => (
                  <li key={n.id}>
                    <Link to={`/reconciliation?noticeId=${encodeURIComponent(n.id)}`}>
                      <span className="mono">{n.noticeNumber ?? n.id}</span> · {n.noticeType ?? "UNKNOWN"} ·{" "}
                      {n.taxPeriod ?? "–"}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      ) : loading ? (
        <LoadingState label="Loading reconciliation" />
      ) : error ? (
        <ErrorState message={error} />
      ) : notice ? (
        <>
          <div className="grid g2" style={{ marginBottom: 16 }}>
            <Card title="Notice difference">
              <div className="cb">
                <span className="mono" style={{ fontSize: 20 }}>
                  {formatINR(result?.noticeDifference ?? notice.differenceAmount)}
                </span>
              </div>
            </Card>
            <Card title="Calculated difference">
              <div className="cb">
                <span className="mono" style={{ fontSize: 20 }}>
                  {result ? formatINR(result.calculatedDifference) : "–"}
                </span>
              </div>
            </Card>
            <Card title="Explained">
              <div className="cb">
                <span className="mono" style={{ fontSize: 20 }}>
                  {result ? formatINR(result.explainedAmount) : "–"}
                </span>
              </div>
            </Card>
            <Card title="Unexplained">
              <div className="cb">
                <span className="mono" style={{ fontSize: 20 }}>
                  {result ? formatINR(result.unexplainedAmount) : "–"}
                </span>
              </div>
            </Card>
          </div>

          {missing.length > 0 ? (
            <Card title="Missing data">
              <div className="cb">
                <EmptyState
                  title="Return data incomplete"
                  description={`Upload ${missing.join(" and ")} for the notice period to run this reconciliation.`}
                  action={
                    <Link className="btn" to={`/notices/${notice.id}`}>
                      Go to notice workspace
                    </Link>
                  }
                />
              </div>
            </Card>
          ) : null}

          <section className="card">
            <div className="ch">
              <span className="h2s">
                Findings {result ? <StatusBadge label={result.status ?? "–"} tone={findingTone(result.status)} /> : null}
              </span>
              {result?.ruleVersion ? <span className="mono sub">rules {result.ruleVersion}</span> : null}
            </div>
            <ReconciliationTable
              findings={result?.findings ?? []}
              selectedId={selectedFinding?.id}
              onSelect={onSelectFinding}
            />
          </section>

          <div style={{ marginTop: 16 }}>
            <FindingLineageCard
              lineage={lineage}
              loading={lineageLoading}
              error={lineageError}
              onClose={
                selectedFinding
                  ? () => {
                      setSelectedFinding(null);
                      setLineage(null);
                      setLineageError(null);
                    }
                  : undefined
              }
            />
          </div>

          <div className="grid g11" style={{ marginTop: 16 }}>
            <Card title="Rule analysis">
              {result ? (
                <div className="cb">
                  <p style={{ marginTop: 0 }}>
                    {notice.noticeType === "DRC-01B"
                      ? "DRC-01B (Rule 88C): GSTR-1 liability minus GSTR-3B liability for the notice period."
                      : notice.noticeType === "DRC-01C"
                        ? "DRC-01C (Rule 88D): GSTR-3B ITC claimed minus GSTR-2B ITC available for the notice period."
                        : "This notice type is not covered by the deterministic engine."}
                  </p>
                  <p className="sub" style={{ marginBottom: 0 }}>
                    Deterministic Python rules, version {result.ruleVersion ?? "–"}. No estimates are generated.
                  </p>
                </div>
              ) : (
                <EmptyState
                  title="No analysis"
                  description="Select a finding after reconciliation to see the rule applied."
                />
              )}
            </Card>
            <Card title="Required evidence set">
              {result && result.findings && result.findings.length > 0 ? (
                <div className="cb">
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {result.findings
                      .filter((f) => f.sourceRows && f.sourceRows.length > 0)
                      .slice(0, 8)
                      .map((f) => (
                        <li key={f.id} className="mono">
                          {f.category}: {(f.sourceRows ?? []).slice(0, 3).join(", ")}
                          {(f.sourceRows ?? []).length > 3 ? ` (+${(f.sourceRows ?? []).length - 3} more)` : ""}
                        </li>
                      ))}
                  </ul>
                </div>
              ) : (
                <EmptyState
                  title="No evidence required yet"
                  description="Required records will be listed per finding."
                />
              )}
            </Card>
          </div>
        </>
      ) : null}
    </>
  );
}
