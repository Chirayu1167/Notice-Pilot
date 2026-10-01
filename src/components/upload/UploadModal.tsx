import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { extractDocument, uploadDocument } from "../../services/documents";
import { parseNotice } from "../../services/notices";
import type { Notice } from "../../types";
import { Modal } from "../ui/Modal";
import { StatusBadge } from "../ui/StatusBadge";
import { INGEST_STAGES, Timeline, type TimelineStageState } from "../Timeline";
import { FileUpload, isSupportedFile } from "./FileUpload";
import { noticeStatusTone } from "../notices/noticeStatus";
import { useToast } from "../ui/Toast";

type Stage = "select" | "uploading" | "extracting" | "parsing" | "done" | "failed";

export function UploadModal({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<Stage>("select");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const { showToast } = useToast();
  const navigate = useNavigate();

  const onFile = (next: File | null) => {
    if (next && !isSupportedFile(next)) {
      showToast("Only PDF or TXT files are accepted");
      return;
    }
    setFile(next);
  };

  const fail = (message: string) => {
    setFailure(message);
    setStage("failed");
    showToast(message);
  };

  const processFile = async () => {
    if (!file) return;
    setFailure(null);
    setNotice(null);
    try {
      setStage("uploading");
      const upload = await uploadDocument(file);
      const documentId = upload.document.id;

      setStage("extracting");
      const extraction = await extractDocument(documentId);
      if (extraction.status !== "EXTRACTED") {
        fail(extraction.message ?? "Text extraction failed.");
        return;
      }

      setStage("parsing");
      const parsed = await parseNotice(documentId);
      setNotice(parsed);
      setStage("done");
      showToast("Notice processed");
    } catch (error) {
      fail(error instanceof Error ? error.message : "Processing failed. Please try again.");
    }
  };

  const viewNotice = () => {
    if (!notice) return;
    onClose();
    navigate(`/notices/${notice.id}`);
  };

  const activeIndex =
    stage === "uploading" ? 0 : stage === "extracting" ? 1 : stage === "parsing" ? 2 : -1;

  const stageStates: TimelineStageState[] = INGEST_STAGES.map((_, i) => {
    if (stage === "done") return "done";
    if (stage === "failed") return i <= Math.max(activeIndex, 0) ? "done" : "waiting";
    if (i < activeIndex) return "done";
    if (i === activeIndex) return "running";
    return "waiting";
  });

  const notes = INGEST_STAGES.map((name, i) => {
    if (stage === "done") {
      return name === "Completed" ? `${notice?.status ?? "Processed"}` : "Complete";
    }
    if (stage === "failed") {
      return i === Math.max(activeIndex, 0) ? (failure ?? "Failed") : i < activeIndex ? "Complete" : "Not reached";
    }
    if (i < activeIndex) return "Complete";
    if (i === activeIndex) {
      return stage === "uploading" ? "Uploading file" : stage === "extracting" ? "Reading document" : "Parsing fields";
    }
    return file ? "Ready" : "Waiting for a file";
  });

  const busy = stage === "uploading" || stage === "extracting" || stage === "parsing";

  return (
    <Modal
      title="Upload GST notice"
      subtitle="Upload the notice you received from the GST portal."
      onClose={onClose}
      closeOnEscape={!busy}
      actions={
        stage === "done" ? (
          <>
            <button type="button" className="btn" onClick={onClose}>
              Close
            </button>
            <button type="button" className="btn t" onClick={viewNotice}>
              View notice
            </button>
          </>
        ) : stage === "failed" ? (
          <button type="button" className="btn n" onClick={onClose}>
            Close
          </button>
        ) : busy ? undefined : (
          <>
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="button" className="btn t" disabled={!file} onClick={processFile}>
              Process notice
            </button>
          </>
        )
      }
    >
      {stage === "done" && notice ? (
        <div className="cb">
          <StatusBadge label="Notice processed" tone="ok" />{" "}
          <StatusBadge label={notice.status ?? "Processed"} tone={noticeStatusTone(notice.status)} />
          <p>
            <b className="mono">{file?.name}</b> was processed
            {notice.noticeType && notice.noticeType !== "UNKNOWN" ? (
              <>
                {" "}as <b className="mono">{notice.noticeType}</b>
              </>
            ) : null}
            {notice.status === "UNSUPPORTED"
              ? ". The document does not appear to be a supported GST notice."
              : "."}
          </p>
          <Timeline stages={INGEST_STAGES} stageStates={stageStates} notes={notes} />
        </div>
      ) : stage === "failed" ? (
        <div className="cb">
          <StatusBadge label="Processing failed" tone="err" />
          <p>{failure}</p>
          <Timeline stages={INGEST_STAGES} stageStates={stageStates} notes={notes} />
        </div>
      ) : busy ? (
        <div className="cb">
          <Timeline stages={INGEST_STAGES} stageStates={stageStates} notes={notes} />
        </div>
      ) : (
        <FileUpload file={file} onFile={onFile} />
      )}
    </Modal>
  );
}
