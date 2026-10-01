import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUploadModal } from "../components/upload/uploadContext";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Tabs } from "../components/ui/Tabs";
import { NoticeTable } from "../components/notices/NoticeTable";
import { LoadingState, ErrorState } from "../components/ui/StateView";
import { listNotices } from "../services/notices";
import type { Notice } from "../types";

export function NoticesPage() {
  const { openUpload } = useUploadModal();
  const navigate = useNavigate();
  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listNotices()
      .then((data) => {
        if (!cancelled) setNotices(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load notices.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <PageHeader
        crumb="Workspace / Notices"
        title="Notices"
        subtitle="All notices received from the GST portal."
        actions={
          <button type="button" className="btn t" onClick={openUpload}>
            Upload notice
          </button>
        }
      />
      <Card
        title="Notice register"
        actions={<Tabs options={["All", "Action required", "Draft ready", "Resolved"]} disabled />}
      >
        {error ? (
          <ErrorState message={error} />
        ) : notices === null ? (
          <LoadingState label="Loading notices" />
        ) : (
          <NoticeTable
            notices={notices}
            onUpload={openUpload}
            onOpen={(id) => navigate(`/notices/${id}`)}
          />
        )}
      </Card>
    </>
  );
}
