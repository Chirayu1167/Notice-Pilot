import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { StatusBadge } from "../ui/StatusBadge";
import { LoadingState } from "../ui/StateView";
import { formatINR } from "./ReconciliationTable";
import {
  downloadReturnFileUrl,
  listReturnData,
  missingSources,
  requiredSources,
  runReconciliation,
  uploadReturnData,
} from "../../services/reconciliation";
import type { Notice, ReconciliationResult, ReturnData } from "../../types";

const RETURN_ACCEPT = ".csv,.xlsx";

function isReturnFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".csv") || name.endsWith(".xlsx");
}

function periodTone(status?: string): "ok" | "err" | "warn" {
  if (status === "MATCH") return "ok";
  if (status === "MISMATCH") return "err";
  return "warn";
}

export function ReturnDataSection({ notice }: { notice: Notice }) {
  const [returns, setReturns] = useState<ReturnData[] | null>(null);
  const [result, setResult] = useState<ReconciliationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState("AUTO");
  const [period, setPeriod] = useState("");

  const noticeId = notice.id;

  const refresh = async () => {
    setReturns(await listReturnData(noticeId));
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listReturnData(noticeId)
      .then((data) => {
        if (!cancelled) setReturns(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load return data.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [noticeId]);

  const onUpload = async (file: File) => {
    if (!isReturnFile(file)) {
      setError("Only CSV or XLSX return files are accepted.");
      return;
    }
    setBusy("upload");
    setError(null);
    try {
      await uploadReturnData(noticeId, file, {
        source,
        period: period.trim() || undefined,
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Return upload failed.");
    } finally {
      setBusy(null);
    }
  };

  const onRun = async () => {
    setBusy("run");
    setError(null);
    try {
      setResult(await runReconciliation(noticeId));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reconciliation failed.");
    } finally {
      setBusy(null);
    }
  };

  const required = requiredSources(notice.noticeType);
  const missing = missingSources(notice.noticeType, returns ?? []);
  const canRun = required.length > 0 && missing.length === 0;

  return (
    <Card title="Return data">
      <div className="cb">
        {loading ? (
          <LoadingState label="Loading return data" />
        ) : returns && returns.length > 0 ? (
          <div className="tw">
          <table aria-label="Uploaded return data">
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">Source</th>
                <th scope="col">Period</th>
                <th scope="col" className="r">Rows</th>
                <th scope="col">Status</th>
                <th scope="col">Original</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.filename ?? r.id}</td>
                  <td className="mono">{r.source ?? "–"}</td>
                  <td className="mono">
                    {r.period ?? "–"}{" "}
                    {r.periodStatus ? (
                      <StatusBadge label={r.periodStatus} tone={periodTone(r.periodStatus)} />
                    ) : null}
                  </td>
                  <td className="mono r">{r.rowCount ?? "–"}</td>
                  <td>
                    <StatusBadge label={r.status ?? "–"} tone="ok" />
                  </td>
                  <td>
                    {r.downloadUrl ? (
                      <a href={downloadReturnFileUrl(r.downloadUrl)} target="_blank" rel="noreferrer">
                        Download
                      </a>
                    ) : (
                      <span className="sub">–</span>
                    )}
                  </td>
                </tr>
              ))}
              </tbody>
          </table>
          </div>
        ) : (
          <EmptyState
            title="No return data yet"
            description="Upload GSTR-1, GSTR-3B or GSTR-2B as CSV or XLSX for the notice period."
          />
        )}

        {required.length === 0 ? (
          <p className="sub" style={{ marginTop: 12 }}>
            This notice type ({notice.noticeType ?? "UNKNOWN"}) is not covered by the deterministic
            reconciliation engine (supports DRC-01B and DRC-01C only).
          </p>
        ) : missing.length > 0 ? (
          <p className="sub" style={{ marginTop: 12 }}>
            Upload {missing.join(" and ")} for the notice period ({notice.taxPeriod ?? "unknown period"})
            to run this reconciliation.
          </p>
        ) : null}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12, alignItems: "center" }}>
          <label className="sub" htmlFor="return-source">
            Return type
          </label>
          <select
            id="return-source"
            value={source}
            disabled={busy !== null}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="AUTO">Auto-detect</option>
            <option value="GSTR-1">GSTR-1</option>
            <option value="GSTR-3B">GSTR-3B</option>
            <option value="GSTR-2B">GSTR-2B</option>
          </select>
          <label className="sub" htmlFor="return-period">
            Period (YYYY-MM, optional)
          </label>
          <input
            id="return-period"
            className="mono"
            style={{ width: 110 }}
            placeholder={notice.taxPeriod ?? "2024-04"}
            value={period}
            disabled={busy !== null}
            onChange={(e) => setPeriod(e.target.value)}
          />
          <label className="btn" aria-disabled={busy !== null}>
            {busy === "upload" ? "Uploading…" : "Upload CSV / XLSX"}
            <input
              type="file"
              accept={RETURN_ACCEPT}
              hidden
              disabled={busy !== null}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void onUpload(file);
              }}
            />
          </label>
          <button type="button" className="btn t" disabled={!canRun || busy !== null} onClick={() => void onRun()}>
            {busy === "run" ? "Running…" : "Run reconciliation"}
          </button>
        </div>

        {error ? (
          <p role="alert" style={{ color: "var(--err, #b3261e)" }}>
            {error}
          </p>
        ) : null}

        {result ? (
          <div style={{ marginTop: 12 }}>
            <p style={{ margin: "0 0 8px" }}>
              <StatusBadge
                label={result.status ?? "–"}
                tone={result.status === "MATCHED" ? "ok" : result.status === "MISSING_DATA" ? "warn" : "err"}
              />{" "}
              <span className="mono">
                Notice {formatINR(result.noticeDifference)} · Calculated {formatINR(result.calculatedDifference)} ·
                Explained {formatINR(result.explainedAmount)} · Unexplained {formatINR(result.unexplainedAmount)}
              </span>
            </p>
            <p style={{ margin: 0 }}>
              <Link to={`/reconciliation?noticeId=${encodeURIComponent(noticeId)}`}>
                View findings ({result.findings?.length ?? 0})
              </Link>
            </p>
          </div>
        ) : (
          <p style={{ marginBottom: 0 }}>
            <Link to={`/reconciliation?noticeId=${encodeURIComponent(noticeId)}`}>
              Open reconciliation workspace
            </Link>
          </p>
        )}
      </div>
    </Card>
  );
}
