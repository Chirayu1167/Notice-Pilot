import { useNavigate } from "react-router-dom";
import { useUploadModal } from "../components/upload/uploadContext";
import { PageHeader } from "../components/ui/PageHeader";
import { ReviewBanner } from "../components/ui/ReviewBanner";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Tabs } from "../components/ui/Tabs";
import { NoticeTable } from "../components/notices/NoticeTable";
import { DemoPanel } from "../components/demo/DemoPanel";

const STRIP = [
  ["Notice intake", "Upload and read"],
  ["Reconcile", "Return data comparison"],
  ["Evidence", "Invoices and records"],
  ["Reply", "Review-ready draft"],
];

function Stat({ label, value, unit, a, b }: { label: string; value: string; unit: string; a: string; b: string }) {
  return (
    <div className="card stat">
      <div className="lbl">{label}</div>
      <div className="big">
        {value}
        <small>{unit}</small>
      </div>
      <div className="row">
        <span>{a}</span>
        <span className="mono">{b}</span>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { openUpload } = useUploadModal();

  return (
    <>
      <PageHeader
        crumb="Overview / Compliance deck"
        title="Dashboard"
        subtitle="Review your GST notices and response workflow."
        actions={<span className="badge">Active GSTIN: not set</span>}
      />
      <ReviewBanner />
      <div style={{ margin: "16px 0" }}>
        <DemoPanel onNotice={(id) => navigate(`/notices/${id}`)} />
      </div>
      <div className="card strip">
        {STRIP.map(([name, desc], i) => (
          <div key={name} className={`step ${i === 0 ? "on" : ""}`}>
            <span className="n">0{i + 1}</span>
            <div>
              <b>{name}</b>
              <small>{desc}</small>
            </div>
          </div>
        ))}
      </div>
      <div className="grid g4">
        <Stat label="Active notices" value="0" unit="none open" a="No urgent items" b="–" />
        <Stat label="Deadlines" value="0" unit="none tracked" a="Set from notice" b="–" />
        <Stat label="Under review" value="0" unit="files" a="Nothing waiting" b="–" />
        <Stat label="Replies ready" value="0" unit="drafts" a="Nothing drafted" b="–" />
      </div>
      <div className="alert">
        <span className="t">Action required</span>
        <h2 className="h2s">No notice needs action</h2>
        <p className="sub">Upload a GST notice to begin your first review. Details will fill in after processing.</p>
        <div className="f">
          {["Notice amount", "Tax period", "Deadline", "Issuing authority"].map((k) => (
            <div key={k}>
              <div className="lbl">{k}</div>
              <span className="ph-v" />
            </div>
          ))}
        </div>
      </div>
      <div className="grid g11">
        <Card title="Deadlines">
          <EmptyState
            title="No deadlines to track"
            description="Deadlines will appear after a notice is processed."
          />
        </Card>
        <Card title="Recent activity">
          <EmptyState title="No activity yet" description="Your processing history will appear here." />
        </Card>
      </div>
      <div style={{ height: 16 }} />
      <Card
        title="Recent notices"
        actions={
          <>
            <span className="badge">0 files</span>
            <Tabs options={["All", "Action required", "Draft ready", "Resolved"]} disabled />
          </>
        }
      >
        <NoticeTable onUpload={openUpload} onOpen={(id) => navigate(`/notices/${id}`)} />
      </Card>
    </>
  );
}
