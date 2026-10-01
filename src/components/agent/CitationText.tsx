import { useState } from "react";
import { Link } from "react-router-dom";
import { getRuleMetadata } from "../../services/agent";

const CITATION_RE = /\[(Finding|Evidence|Rule)\s+([^\]]+)\]/g;

export function CitationText({ text, noticeId }: { text: string; noticeId: string }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  CITATION_RE.lastIndex = 0;
  while ((match = CITATION_RE.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const [, kind, ref] = match;
    if (kind === "Finding") {
      parts.push(
        <Link key={key++} className="mono" to={`/reconciliation?noticeId=${encodeURIComponent(noticeId)}&finding=${encodeURIComponent(ref.trim())}`}>
          [Finding {ref.trim()}]
        </Link>
      );
    } else if (kind === "Evidence") {
      parts.push(
        <Link key={key++} className="mono" to={`/evidence?noticeId=${encodeURIComponent(noticeId)}`}>
          [Evidence {ref.trim()}]
        </Link>
      );
    } else {
      parts.push(<RuleCitation key={key++} refText={ref.trim()} />);
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}

function RuleCitation({ refText }: { refText: string }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<string | null>(null);
  const toggle = () => {
    if (!open) {
      getRuleMetadata()
        .then((meta) => {
          const hit = meta.sources.find((s) => refText.includes(s.rule.replace("CGST ", "")));
          setDetail(
            hit
              ? `${hit.rule}: ${hit.relationship} Formula: ${hit.formula} (rules ${meta.ruleVersion})`
              : `Rule metadata version ${meta.ruleVersion}.`
          );
        })
        .catch(() => setDetail("Rule metadata unavailable."));
    }
    setOpen(!open);
  };
  return (
    <span>
      <button type="button" className="btn mono" style={{ padding: "0 6px", fontSize: 12 }} onClick={toggle}>
        [Rule {refText}]
      </button>
      {open ? <span className="sub" style={{ marginLeft: 6 }}>{detail ?? "Loading rule…"}</span> : null}
    </span>
  );
}
