type DocumentPreviewProps = {
  title?: string;
  description?: string;
  text?: string;
  pdfUrl?: string;
};

export function DocumentPreview({ title, description, text, pdfUrl }: DocumentPreviewProps) {
  if (pdfUrl) {
    return (
      <div className="viewer">
        <iframe
          title={title ?? "Source document"}
          src={pdfUrl}
          className="docframe"
        />
      </div>
    );
  }
  if (text) {
    return (
      <div className="viewer">
        <pre className="doctext mono">{text}</pre>
      </div>
    );
  }
  return (
    <div className="viewer">
      <div className="page" style={{ display: "grid", placeItems: "center", textAlign: "center", color: "var(--mut)" }}>
        <div>
          <b className="ser" style={{ fontSize: 18, color: "var(--pri)" }}>
            {title ?? "No document loaded"}
          </b>
          <br />
          {description ?? "The uploaded notice will be shown here."}
        </div>
      </div>
    </div>
  );
}
