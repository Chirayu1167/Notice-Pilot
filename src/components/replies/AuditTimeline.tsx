import { useEffect, useState } from "react";
import { Card } from "../ui/Card";
import { LoadingState } from "../ui/StateView";
import { getNoticeAudit } from "../../services/agent";
import type { AuditEvent } from "../../types";

function timeOf(iso?: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso.replace(" ", "T") + (iso.includes("T") ? "" : "Z"));
  if (Number.isNaN(d.getTime())) return iso.slice(11, 16) || iso;
  return d.toTimeString().slice(0, 5);
}

function actionLabel(action: string): string {
  return action
    .split("_")
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(" ");
}

export function AuditTimeline({ noticeId, compact }: { noticeId: string; compact?: boolean }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getNoticeAudit(noticeId)
      .then((data) => {
        if (!cancelled) setEvents(data);
      })
      .catch(() => {
        if (!cancelled) setEvents([]);
      });
    return () => {
      cancelled = true;
    };
  }, [noticeId]);

  const shown = compact && events ? events.slice(-8) : events;

  return (
    <Card title="Audit trail">
      <div className="cb">
        {!shown ? (
          <LoadingState label="Loading audit trail" />
        ) : shown.length === 0 ? (
          <p className="sub" style={{ margin: 0 }}>
            No audit events yet.
          </p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {shown.map((e) => (
              <li key={e.id} style={{ marginBottom: 4 }}>
                <span className="mono">{timeOf(e.createdAt)}</span> {actionLabel(e.action)}{" "}
                <span className="badge">{e.actorType}</span>
              </li>
            ))}
          </ul>
        )}
        {compact && events && events.length > 8 ? (
          <p className="sub" style={{ marginBottom: 0 }}>
            Showing latest 8 of {events.length} events.
          </p>
        ) : null}
      </div>
    </Card>
  );
}
