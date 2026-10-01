import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Tabs } from "../components/ui/Tabs";
import { DataTable } from "../components/ui/DataTable";
import { StatusBadge } from "../components/ui/StatusBadge";
import { LoadingState, ErrorState } from "../components/ui/StateView";
import { getNoticeEvidence, type NoticeEvidence } from "../services/agent";

export function EvidencePage() {
  const [params] = useSearchParams();
  const noticeId = params.get("noticeId") ?? "";
  const [evidence, setEvidence] = useState<NoticeEvidence | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!noticeId) return;
    getNoticeEvidence(noticeId)
      .then(setEvidence)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load evidence."));
  }, [noticeId]);

  const rows = [
    ...(evidence?.verified ?? []).map((e) => ({ ...e, state: "verified" as const })),
    ...(evidence?.partial ?? []).map((e) => ({ ...e, state: "partial" as const })),
  ];

  return (
    <>
      <PageHeader
        crumb="Workspace / Evidence"
        title="Evidence"
        subtitle="Supporting records linked to reconciliation findings."
        actions={
          noticeId ? (
            <Link className="btn" to={`/notices/${noticeId}`}>
              Back to notice
            </Link>
          ) : undefined
        }
      />
      <Card
        title="Evidence index"
        actions={<Tabs options={["All", "Attached", "Unlinked"]} disabled />}
      >
        {!noticeId ? (
          <div className="cb">
            <p className="sub" style={{ margin: 0 }}>
              Open evidence from a notice workspace to see its verified, partial and missing records.
            </p>
          </div>
        ) : error ? (
          <ErrorState message={error} />
        ) : !evidence ? (
          <LoadingState label="Loading evidence" />
        ) : (
          <DataTable
            columns={["ID", "Document", "Finding", "Source", "Status"]}
            emptyTitle="No evidence collected"
            emptyDescription="Evidence will appear when processed records are linked to a finding."
            footer={
              <>
                <span>{rows.length} records</span>
                <span>{evidence.missing.length} missing</span>
              </>
            }
          >
            {rows.map((item) => (
              <tr key={item.evidenceId}>
                <td className="mono">{item.evidenceId}</td>
                <td className="mono">{item.filename}</td>
                <td>
                  <Link
                    className="mono"
                    to={`/reconciliation?noticeId=${encodeURIComponent(noticeId)}`}
                  >
                    View findings
                  </Link>
                </td>
                <td className="mono">{item.source}</td>
                <td>
                  <StatusBadge label={item.state} tone={item.state === "verified" ? "ok" : "warn"} />
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </Card>
      {evidence && evidence.missing.length > 0 ? (
        <Card title="Missing evidence">
          <div className="cb">
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {evidence.missing.map((m, i) => (
                <li key={i} className="sub">
                  {m.source ? <span className="mono">{m.source}</span> : m.type}
                  {m.amount ? ` — ₹${Number(m.amount).toLocaleString("en-IN")}` : ""}: {m.reason}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      ) : null}
    </>
  );
}
