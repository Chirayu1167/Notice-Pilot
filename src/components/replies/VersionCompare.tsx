import { useState } from "react";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/StateView";
import { StatusBadge } from "../ui/StatusBadge";
import { compareVersions, type VersionCompare } from "../../services/agent";
import type { DraftVersion } from "../../types";

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "–";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function VersionCompareView({ draftId, versions }: { draftId: string; versions: DraftVersion[] }) {
  const [from, setFrom] = useState<number>(1);
  const [to, setTo] = useState<number>(Math.max(2, ...versions.map((v) => v.version)));
  const [result, setResult] = useState<VersionCompare | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (versions.length < 2) return null;

  const onCompare = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await compareVersions(draftId, from, to));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Compare versions">
      <div className="cb">
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <label className="sub" htmlFor="compare-from">
            Compare
            <select
              id="compare-from"
              value={from}
              onChange={(e) => setFrom(Number(e.target.value))}
              style={{ marginLeft: 4 }}
            >
              {versions.map((v) => (
                <option key={v.id} value={v.version}>
                  v{v.version}
                </option>
              ))}
            </select>
          </label>
          <span className="sub" aria-hidden>
            →
          </span>
          <label className="sub" htmlFor="compare-to">
            <select
              id="compare-to"
              value={to}
              onChange={(e) => setTo(Number(e.target.value))}
              aria-label="Compare to version"
            >
              {versions.map((v) => (
                <option key={v.id} value={v.version}>
                  v{v.version}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn" disabled={loading} onClick={() => void onCompare()}>
            {loading ? "Comparing…" : `Compare v${from} → v${to}`}
          </button>
        </div>
        {loading ? <LoadingState label="Comparing versions" /> : null}
        {error ? (
          <p role="alert" style={{ color: "var(--err, #b3261e)" }}>
            {error}
          </p>
        ) : null}
        {result && !loading ? (
          <div style={{ marginTop: 8 }}>
            {!result.hasChanges ? (
              <EmptyState title="No changes" description={`v${from} and v${to} are identical in content and references.`} />
            ) : (
              <>
                <b>Content changes</b>
                {result.contentChanges.length === 0 ? (
                  <p className="sub">No text changes.</p>
                ) : (
                  <ul style={{ paddingLeft: 18 }}>
                    {result.contentChanges.map((c, i) => (
                      <li key={i} style={{ marginBottom: 6 }}>
                        <StatusBadge
                          label={c.kind}
                          tone={c.kind.includes("added") ? "ok" : c.kind.includes("removed") ? "err" : "warn"}
                        />
                        {(c.old ?? []).map((line, j) => (
                          <div key={`o${j}`} className="mono" style={{ textDecoration: "line-through" }}>
                            − {line}
                          </div>
                        ))}
                        {(c.new ?? []).map((line, j) => (
                          <div key={`n${j}`} className="mono">
                            + {line}
                          </div>
                        ))}
                        {c.note ? <div className="sub">{c.note}</div> : null}
                      </li>
                    ))}
                  </ul>
                )}
                <b>Structured changes</b>
                <ul style={{ paddingLeft: 18 }}>
                  {result.structuredChanges.map((s) => (
                    <li key={s.field} style={{ marginBottom: 4 }}>
                      <span className="mono">{s.field}</span>{" "}
                      <span className="sub">({s.kind})</span>{" "}
                      {s.changed ? (
                        <StatusBadge label="changed" tone="warn" />
                      ) : (
                        <StatusBadge label="unchanged" tone="ok" />
                      )}
                      {s.changed ? (
                        <div className="mono sub">
                          {s.added || s.removed ? (
                            <>
                              {s.added && s.added.length > 0 ? <div>+ {s.added.join(", ")}</div> : null}
                              {s.removed && s.removed.length > 0 ? (
                                <div>− {s.removed.join(", ")}</div>
                              ) : null}
                            </>
                          ) : s.changedKeys ? (
                            <div>keys: {s.changedKeys.join(", ")}</div>
                          ) : (
                            <div>
                              {renderValue(s.from)} → {renderValue(s.to)}
                            </div>
                          )}
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
