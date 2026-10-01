import { useEffect, useState } from "react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { LoadingState } from "../components/ui/StateView";
import { MetadataRow } from "../components/ui/MetadataRow";
import { StatusBadge } from "../components/ui/StatusBadge";
import { ReviewerSwitcher } from "../components/replies/ReviewerSwitcher";
import { getSystemStatus } from "../services/agent";

type SystemStatus = {
  backend: string;
  database: string;
  storage: boolean;
  agent: { available: boolean; provider?: string; model?: string };
  ruleVersion: string;
  appVersion: string;
};

export function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSystemStatus()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Backend unreachable.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <PageHeader crumb="Workspace / Settings" title="Settings" subtitle="Preferences for this workspace." />
      <div className="grid g2" style={{ alignContent: "start" }}>
        <div className="grid" style={{ alignContent: "start" }}>
          <Card title="Demo reviewer identity">
            <div className="cb">
              <ReviewerSwitcher />
            </div>
          </Card>
          <Card title="Application status">
            <div className="cb">
              {!status && !error ? (
                <LoadingState label="Checking backend status" />
              ) : error ? (
                <p role="alert" style={{ color: "var(--err, #b3261e)" }}>
                  {error}
                </p>
              ) : status ? (
                <>
                  <p style={{ marginTop: 0 }}>
                    <StatusBadge label={status.database === "ok" ? "Backend healthy" : "Backend degraded"} tone={status.database === "ok" ? "ok" : "err"} />{" "}
                    <StatusBadge
                      label={status.agent.available ? `Agent ready (${status.agent.provider ?? "unknown"})` : "Agent unavailable"}
                      tone={status.agent.available ? "ok" : "warn"}
                    />
                  </p>
                  <MetadataRow label="App version" value={status.appVersion} />
                  <MetadataRow label="Rule version" value={status.ruleVersion} />
                  <MetadataRow label="Agent model" value={status.agent.model ?? "–"} />
                </>
              ) : null}
            </div>
          </Card>
        </div>
        <section className="card">
          <div className="set">
            <h2>Profile</h2>
            <div>
              <input type="text" placeholder="Name" aria-label="Name" />
            </div>
          </div>
          <div className="set">
            <h2>Language</h2>
            <div>
              <select aria-label="Language" defaultValue="English">
                <option>English</option>
                <option>Hindi</option>
                <option>Marathi</option>
              </select>
            </div>
          </div>
          <div className="set">
            <h2>Document preferences</h2>
            <div>
              <select aria-label="Export format" defaultValue="PDF">
                <option>PDF</option>
                <option>DOCX</option>
              </select>
            </div>
          </div>
          <div className="set">
            <h2>Review preferences</h2>
            <div>
              <label>
                <input type="checkbox" checked disabled /> Require review before export
              </label>
            </div>
          </div>
          <div className="set">
            <h2>Rule pack</h2>
            <div>
              <span className="sub">Rule pack will be connected in the processing layer.</span>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
