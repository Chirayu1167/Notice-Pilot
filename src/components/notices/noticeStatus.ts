export function noticeStatusTone(status?: string): "default" | "ok" | "warn" | "err" {
  if (status === "VALID") return "ok";
  if (status === "PARTIAL") return "warn";
  if (status === "UNSUPPORTED" || status === "ERROR") return "err";
  return "default";
}
