import { Link } from "react-router-dom";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/StateView";
import { StatusBadge } from "../ui/StatusBadge";
import { Timeline } from "../Timeline";
import {
  downloadNoticeFileUrl,
  downloadReturnFileUrl,
} from "../../services/reconciliation";
import type { FindingLineage } from "../../types";
import { findingTone, formatINR } from "./ReconciliationTable";

function ChainStep({ index, title, children }: { index: number; title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 12 }}>
      <div
        className="mono"
        aria-hidden
        style={{
          flexShrink: 0,
          width: 28,
          height: 28,
          borderRadius: "50%",
          border: "1px solid var(--border, #ccc)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {index + 1}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <b>{title}</b>
        <div style={{ marginTop: 4 }}>{children}</div>
      </div>
    </div>
  );
}

export function FindingLineageView({
  lineage,
  loading,
  error,
}: {
  lineage: FindingLineage | null;
  loading?: boolean;
  error?: string | null;
}) {
  if (loading) return <LoadingState label="Loading evidence chain" />;
  if (error) return <EmptyState title="Chain unavailable" description={error} />;
  if (!lineage) {
    return (
      <EmptyState
        title="No finding selected"
        description="Select a finding in the table above to trace NOTICE → FINDING → CALCULATION → RETURN ROW → SOURCE DOCUMENT → ORIGINAL FILE."
      />
    );
  }

  const { finding, calculation, notice, noticeDocument, returnRows, returnDocuments } = lineage;

  return (
    <div className="grid" style={{ gap: 16 }}>
      <ChainStep index={0} title="NOTICE">
        <Link className="mono" to={`/notices/${encodeURIComponent(notice.id)}`}>
          {notice.noticeNumber ?? notice.id}
        </Link>{" "}
        <span className="mono sub">
          · {notice.noticeType ?? "–"} · Period {notice.taxPeriod ?? "–"} · Difference{" "}
          {formatINR(notice.differenceAmount)}
        </span>{" "}
        {noticeDocument ? (
          <a href={downloadNoticeFileUrl(noticeDocument.id)} target="_blank" rel="noreferrer">
            Original notice file ({noticeDocument.filename ?? "download"})
          </a>
        ) : null}
      </ChainStep>

      <ChainStep index={1} title="FINDING">
        <Link
          className="mono"
          to={`/reconciliation?noticeId=${encodeURIComponent(notice.id)}&finding=${encodeURIComponent(finding.id)}`}
        >
          {finding.id}
        </Link>{" "}
        <span>
          {finding.description ?? "–"}{" "}
          <StatusBadge label={finding.status ?? "–"} tone={findingTone(finding.status)} />
        </span>
      </ChainStep>

      <ChainStep index={2} title="CALCULATION">
        {calculation?.rule || calculation?.formula ? (
          <>
            <div className="mono">{calculation.rule ?? "–"}</div>
            <div className="mono sub">{calculation.formula ?? "–"}</div>
            {calculation.inputs && Object.keys(calculation.inputs).length > 0 ? (
              <dl className="mono" style={{ margin: "4px 0 0", fontSize: 12 }}>
                {Object.entries(calculation.inputs).map(([key, value]) => (
                  <div key={key} style={{ display: "flex", gap: 8 }}>
                    <dt className="sub">{key}</dt>
                    <dd style={{ margin: 0 }}>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {calculation.ruleVersion ? (
              <div className="mono sub">rules {calculation.ruleVersion}</div>
            ) : null}
          </>
        ) : (
          <span className="sub">Recorded before calculation tracking — re-run reconciliation.</span>
        )}
      </ChainStep>

      <ChainStep index={3} title={`RETURN ROW${returnRows.length === 1 ? "" : "S"} (${returnRows.length})`}>
        {returnRows.length > 0 ? (
          <div className="tw">
            <table aria-label="Source return rows">
              <thead>
                <tr>
                  <th scope="col">Row</th>
                  <th scope="col">Source</th>
                  <th scope="col">Invoice</th>
                  <th scope="col">Date</th>
                  <th scope="col" className="r">Taxable</th>
                  <th scope="col" className="r">Total tax</th>
                </tr>
              </thead>
              <tbody>
                {returnRows.slice(0, 25).map((row) => (
                  <tr key={row.id}>
                    <td className="mono" title={row.id}>{row.id.split("-").slice(-1)[0]}</td>
                    <td className="mono">{row.source ?? "–"}</td>
                    <td className="mono">{row.invoiceNumber ?? "–"}</td>
                    <td className="mono">{row.invoiceDate ?? "–"}</td>
                    <td className="mono r">{formatINR(row.taxableValue)}</td>
                    <td className="mono r">{formatINR(row.totalTax)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <span className="sub">No return rows linked (observation finding).</span>
        )}
        {returnRows.length > 25 ? (
          <div className="sub">Showing 25 of {returnRows.length} rows.</div>
        ) : null}
      </ChainStep>

      <ChainStep index={4} title="SOURCE DOCUMENT">
        {returnDocuments.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {returnDocuments.map((doc) => (
              <li key={doc.id} className="mono">
                <Link to={`/evidence?noticeId=${encodeURIComponent(notice.id)}`}>{doc.id}</Link> ·{" "}
                {doc.source} · {doc.filename} · {doc.rowCount} rows · Period {doc.period ?? "–"}
              </li>
            ))}
          </ul>
        ) : (
          <span className="sub">No source document linked.</span>
        )}
      </ChainStep>

      <ChainStep index={5} title="ORIGINAL FILE">
        {returnDocuments.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {returnDocuments.map((doc) => (
              <li key={doc.id}>
                {doc.originalFileStored && doc.downloadUrl ? (
                  <a href={downloadReturnFileUrl(doc.downloadUrl)} target="_blank" rel="noreferrer">
                    <span className="mono">{doc.filename}</span> (byte-identical upload)
                  </a>
                ) : (
                  <span>
                    <span className="mono">{doc.filename}</span>{" "}
                    <span className="sub">— original not stored, re-upload to enable download.</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <span className="sub">No files linked.</span>
        )}
      </ChainStep>
    </div>
  );
}

export function FindingLineageCard(props: {
  lineage: FindingLineage | null;
  loading?: boolean;
  error?: string | null;
  onClose?: () => void;
}) {
  const stages = ["Notice", "Finding", "Calculation", "Return row", "Source document", "Original file"];
  return (
    <Card
      title="Evidence chain"
      actions={props.onClose ? <button type="button" className="btn" onClick={props.onClose}>Clear</button> : undefined}
    >
      <div className="cb">
        <Timeline stages={stages} stageStates={stages.map(() => "done" as const)} notes={[]} />
        <div style={{ marginTop: 12 }}>
          <FindingLineageView lineage={props.lineage} loading={props.loading} error={props.error} />
        </div>
      </div>
    </Card>
  );
}
