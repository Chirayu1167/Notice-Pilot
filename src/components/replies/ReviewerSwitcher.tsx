import { useState } from "react";
import { createReviewer, useReviewers } from "../../services/reviewers";

export function ReviewerSwitcher({ compact }: { compact?: boolean }) {
  const { reviewers, active, activeId, select, refresh, error } = useReviewers();
  const [adding, setAdding] = useState(false);
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const onAdd = async () => {
    setBusy(true);
    setFormError(null);
    try {
      const created = await createReviewer(newId.trim().toLowerCase(), newName.trim());
      setNewId("");
      setNewName("");
      setAdding(false);
      await refresh();
      select(created.id);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not create reviewer.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <label htmlFor="reviewer-select" className="sub">
          Demo reviewer identity
        </label>
        {reviewers === null ? (
          <span className="sub">Loading reviewers…</span>
        ) : (
          <select
            id="reviewer-select"
            value={activeId}
            onChange={(e) => select(e.target.value)}
            aria-label="Active demo reviewer"
          >
            {reviewers.map((r) => (
              <option key={r.id} value={r.id}>
                {r.displayName} ({r.id})
              </option>
            ))}
          </select>
        )}
        {!compact ? (
          <button type="button" className="btn" onClick={() => setAdding(!adding)}>
            {adding ? "Cancel" : "New reviewer"}
          </button>
        ) : null}
      </div>
      {!compact ? (
        <p className="sub" style={{ margin: "4px 0 0" }}>
          Demo identities only — not production authentication. Every review action records the reviewer.
          {active ? (
            <>
              {" "}Active: <b>{active.displayName}</b>
            </>
          ) : null}
        </p>
      ) : null}
      {error ? <p className="sub">{error}</p> : null}
      {adding && !compact ? (
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <label className="sub" htmlFor="reviewer-id">
            ID
            <input
              id="reviewer-id"
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              placeholder="reviewer_2"
              style={{ marginLeft: 4 }}
            />
          </label>
          <label className="sub" htmlFor="reviewer-name">
            Display name
            <input
              id="reviewer-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Second Reviewer"
              style={{ marginLeft: 4 }}
            />
          </label>
          <button type="button" className="btn t" disabled={busy} onClick={() => void onAdd()}>
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      ) : null}
      {formError ? (
        <p role="alert" style={{ color: "var(--err, #b3261e)" }}>
          {formError}
        </p>
      ) : null}
    </div>
  );
}
