import { useRef, useState, type DragEvent } from "react";

const ACCEPTED = [".pdf", ".txt"];

export function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED.some((ext) => name.endsWith(ext));
}

type FileUploadProps = {
  file: File | null;
  onFile: (file: File | null) => void;
  disabled?: boolean;
};

export function FileUpload({ file, onFile, disabled = false }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (candidate: File | undefined | null) => {
    if (!candidate) return;
    onFile(candidate);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    pick(e.dataTransfer.files?.[0]);
  };

  return (
    <div className="cb">
      <label
        className={`drop ${dragging ? "h" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,application/pdf,text/plain"
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        {file ? (
          <>
            <b className="mono">{file.name}</b>
            <br />
            <span className="sub">Ready for processing</span>
          </>
        ) : (
          <>
            <b>Drop your file here or choose a file</b>
            <br />
            <span className="sub">PDF or TXT</span>
          </>
        )}
      </label>
      <div style={{ marginTop: 10, display: "flex", gap: 8, justifyContent: "center" }}>
        <button type="button" className="btn" disabled={disabled} onClick={() => inputRef.current?.click()}>
          {file ? "Choose a different file" : "Choose a file"}
        </button>
        {file ? (
          <button type="button" className="btn" disabled={disabled} onClick={() => onFile(null)}>
            Clear
          </button>
        ) : null}
      </div>
    </div>
  );
}
