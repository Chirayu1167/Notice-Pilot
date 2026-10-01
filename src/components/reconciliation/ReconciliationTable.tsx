import type { Finding } from "../../types";
import { DataTable } from "../ui/DataTable";
import { StatusBadge } from "../ui/StatusBadge";

type ReconciliationTableProps = {
  findings?: Finding[];
  selectedId?: string | null;
  onSelect?: (finding: Finding) => void;
};

export function findingTone(status?: string): "ok" | "err" | "warn" | "default" {
  switch ((status ?? "").toUpperCase()) {
    case "MATCHED":
    case "MATCHED_COMPONENT":
      return "ok";
    case "MISMATCH":
    case "PERIOD_MISMATCH":
      return "err";
    case "MISSING_DATA":
    case "UNSUPPORTED":
      return "warn";
    default:
      return status === "matched" ? "ok" : status === "mismatch" ? "err" : "default";
  }
}

export function formatINR(value?: number | null): string {
  if (value === undefined || value === null) return "–";
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function sourceLabel(finding: Finding): string {
  if (finding.sourceRows && finding.sourceRows.length > 0) {
    if (finding.sourceRows.length <= 2) return finding.sourceRows.join(" → ");
    return `${finding.sourceRows[0]} → … (${finding.sourceRows.length} rows)`;
  }
  if (finding.sourceA !== undefined || finding.sourceB !== undefined) {
    return `${finding.sourceA ?? "–"} / ${finding.sourceB ?? "–"}`;
  }
  return "–";
}

export function ReconciliationTable({ findings = [], selectedId, onSelect }: ReconciliationTableProps) {
  const legacy = findings.some((f) => f.metric !== undefined && f.description === undefined);
  if (legacy) {
    return (
      <DataTable
        columns={["Metric", "Source A", "Source B", "Difference", "Status"]}
        emptyTitle="No reconciliation available"
        emptyDescription="Upload the required return data to begin reconciliation."
        footer={
          <>
            <span>Records: 0 of 0 · Selected: none</span>
            <span>
              Total A: <span className="mono">–</span> · Total B: <span className="mono">–</span> ·
              Net variance: <span className="mono">–</span> · Unresolved: <span className="mono">–</span>
            </span>
          </>
        }
      >
        {findings.map((finding) => (
          <tr key={finding.id}>
            <td>{finding.metric ?? "–"}</td>
            <td className="mono r">{finding.sourceA ?? "–"}</td>
            <td className="mono r">{finding.sourceB ?? "–"}</td>
            <td className="mono r">{finding.difference ?? "–"}</td>
            <td>
              <StatusBadge label={finding.status ?? "–"} tone={findingTone(finding.status)} />
            </td>
          </tr>
        ))}
      </DataTable>
    );
  }

  return (
    <DataTable
      columns={["Finding", "Category", "Amount", "Source", "Status"]}
      emptyTitle="No reconciliation available"
      emptyDescription="Upload the required return data to begin reconciliation."
      footer={
        <span>
          Findings: <span className="mono">{findings.length}</span>
        </span>
      }
    >
      {findings.map((finding) => (
        <tr
          key={finding.id}
          onClick={onSelect ? () => onSelect(finding) : undefined}
          aria-selected={selectedId === finding.id || undefined}
          style={onSelect ? { cursor: "pointer", background: selectedId === finding.id ? "var(--sel, #eef4ff)" : undefined } : undefined}
          title={onSelect ? "Trace evidence chain" : undefined}
        >
          <td>{finding.description ?? "–"}</td>
          <td className="mono">{finding.category ?? "–"}</td>
          <td className="mono r">{formatINR(finding.amount)}</td>
          <td className="mono" title={(finding.sourceRows ?? []).join(", ")}>
            {sourceLabel(finding)}
          </td>
          <td>
            <StatusBadge label={finding.status ?? "–"} tone={findingTone(finding.status)} />
          </td>
        </tr>
      ))}
    </DataTable>
  );
}
