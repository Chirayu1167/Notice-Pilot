type ReplyEditorProps = {
  hasDraft: boolean;
};

export function ReplyEditor({ hasDraft }: ReplyEditorProps) {
  return (
    <section className="card">
      <div className="tool">
        {["B", "I", "U", "•", "1."].map((mark) => (
          <button key={mark} type="button" disabled aria-label={`Format ${mark}`}>
            {mark}
          </button>
        ))}
        <span className="badge" style={{ marginLeft: "auto" }}>
          {hasDraft ? "Draft" : "No draft"}
        </span>
      </div>
      <div className="viewer" style={{ border: 0, borderRadius: 0 }}>
        <div className="page">
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <div className="lbl">Response document</div>
            <b className="ser" style={{ fontSize: 22, color: "var(--pri)" }}>
              No response draft
            </b>
            <p className="sub">Complete a reconciliation before preparing a response.</p>
          </div>
          <div className="rule l" />
          <div className="rule l" />
          <div className="rule" />
        </div>
      </div>
      <div className="verify">
        <div className="lbl" style={{ marginBottom: 8 }}>
          Reviewer verification
        </div>
        <label>
          <input type="checkbox" disabled /> A reviewer confirms the reconciliation and evidence here, once a draft
          exists.
        </label>
      </div>
    </section>
  );
}
