import { StatusBadge } from "./StatusBadge";

export type DeadlineInfo = {
  kind: "none" | "overdue" | "urgent" | "upcoming" | "unparseable";
  daysRemaining: number | null;
  label: string;
};

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const d = new Date(`${value}T00:00:00`);
  if (!Number.isNaN(d.getTime())) return d;
  const fallback = new Date(value);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Deterministic deadline derivation: same (dueDate, now) always yields the same result. */
export function deadlineInfo(dueDate?: string | null, now?: Date): DeadlineInfo {
  const due = parseDate(dueDate);
  if (!due) {
    return dueDate
      ? { kind: "unparseable", daysRemaining: null, label: `Due date not parseable: ${dueDate}` }
      : { kind: "none", daysRemaining: null, label: "No deadline" };
  }
  const today = startOfDay(now ?? new Date());
  const days = Math.round((startOfDay(due).getTime() - today.getTime()) / 86400000);
  if (days < 0) {
    return { kind: "overdue", daysRemaining: days, label: `Overdue by ${-days} day${-days === 1 ? "" : "s"}` };
  }
  if (days === 0) return { kind: "urgent", daysRemaining: 0, label: "Due today" };
  if (days <= 7) {
    return { kind: "urgent", daysRemaining: days, label: `${days} day${days === 1 ? "" : "s"} remaining` };
  }
  return { kind: "upcoming", daysRemaining: days, label: `${days} days remaining` };
}

export function DeadlineBadge({ dueDate, now }: { dueDate?: string | null; now?: Date }) {
  const info = deadlineInfo(dueDate, now);
  const tone = info.kind === "overdue" ? "err" : info.kind === "urgent" ? "warn" : info.kind === "none" ? "default" : "ok";
  const text = info.kind === "none" || info.kind === "unparseable" ? info.label : `${dueDate} · ${info.label}`;
  return <StatusBadge label={text} tone={tone} />;
}
