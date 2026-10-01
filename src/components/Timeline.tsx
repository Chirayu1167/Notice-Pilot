export const STAGES = [
  "Upload",
  "Read document",
  "Extract fields",
  "Reconcile",
  "Check evidence",
  "Prepare review",
] as const;

export type TimelineStageState = "waiting" | "running" | "done";

export const INGEST_STAGES = ["Upload", "Extraction", "Parsing", "Completed"] as const;

type TimelineProps = {
  stages?: readonly string[];
  stageStates: TimelineStageState[];
  notes?: string[];
};

export function Timeline({ stages = STAGES, stageStates, notes }: TimelineProps) {
  return (
    <ol className="tl">
      {stages.map((name, i) => {
        const state = stageStates[i] ?? "waiting";
        const note = notes?.[i] ?? (state === "done" ? "Complete" : "Not connected");
        return (
          <li key={name}>
            <span className={`dot ${state === "done" ? "done" : state === "running" ? "run" : ""}`} />
            <div>
              <b>{name}</b>
              <small>{note}</small>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
