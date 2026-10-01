import type { Notice } from "../../types";
import { DataTable } from "../ui/DataTable";
import { DeadlineBadge } from "../ui/DeadlineBadge";
import { StatusBadge } from "../ui/StatusBadge";
import { noticeStatusTone } from "./noticeStatus";

type NoticeTableProps = {
  notices?: Notice[];
  onUpload: () => void;
  onOpen?: (id: string) => void;
};

export function formatAmount(value?: number | null): string {
  if (value === undefined || value === null) return "–";
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function NoticeTable({ notices = [], onUpload, onOpen }: NoticeTableProps) {
  const count = notices.length;
  return (
    <DataTable
      columns={["Notice", "Type", "Tax period", "Difference", "Due date", "Status", "Actions"]}
      emptyTitle="No notices found"
      emptyDescription="Upload a GST notice to start."
      emptyAction={
        <button type="button" className="btn n" onClick={onUpload}>
          Upload notice
        </button>
      }
      footer={
        <>
          <span>
            Showing {count} of {count} notices
          </span>
          <span />
        </>
      }
    >
      {notices.map((notice) => (
        <tr key={notice.id}>
          <td className="mono">{notice.noticeNumber ?? notice.id}</td>
          <td className="mono">{notice.noticeType ?? notice.type ?? "–"}</td>
          <td className="mono">{notice.taxPeriod ?? "–"}</td>
          <td className="mono r">{formatAmount(notice.differenceAmount)}</td>
          <td>
            <DeadlineBadge dueDate={notice.dueDate} />
          </td>
          <td>
            <StatusBadge label={notice.status ?? "–"} tone={noticeStatusTone(notice.status)} />
          </td>
          <td>
            <button type="button" className="btn" onClick={() => onOpen?.(notice.id)}>
              Open
            </button>
          </td>
        </tr>
      ))}
    </DataTable>
  );
}
