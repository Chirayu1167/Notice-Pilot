import type { EvidenceItem } from "../../types";
import { StatusBadge } from "../ui/StatusBadge";

type EvidenceRowProps = {
  item: EvidenceItem;
};

export function EvidenceRow({ item }: EvidenceRowProps) {
  return (
    <tr>
      <td className="mono">{item.id}</td>
      <td>{item.documentId ?? "–"}</td>
      <td className="mono">{item.findingId ?? "–"}</td>
      <td>{item.source ?? "–"}</td>
      <td>
        <StatusBadge
          label={item.status ?? "–"}
          tone={item.status === "attached" ? "ok" : item.status === "pending" ? "warn" : "default"}
        />
      </td>
    </tr>
  );
}
