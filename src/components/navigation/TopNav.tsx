import { NavLink } from "react-router-dom";
import { useToast } from "../ui/Toast";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/notices", label: "Notices" },
  { to: "/reconciliation", label: "Reconciliation" },
  { to: "/evidence", label: "Evidence" },
  { to: "/replies", label: "Replies" },
  { to: "/settings", label: "Settings" },
];

export function TopNav({ onUpload }: { onUpload: () => void }) {
  const { showToast } = useToast();

  return (
    <header className="topnav">
      <div className="bar">
        <NavLink className="logo" to="/dashboard">
          <i aria-hidden="true" />
          NoticePilot
        </NavLink>
        <div className="gs">
          <span className="lbl" style={{ fontSize: 10 }}>
            GSTIN
          </span>
          <b>None added</b>
        </div>
        <nav className="mainnav" aria-label="Main">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <label className="srch">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-4-4" />
          </svg>
          <input placeholder="Search notices, GSTIN, DIN…" aria-label="Search" disabled />
          <kbd>Ctrl K</kbd>
        </label>
        <button type="button" className="btn t" onClick={onUpload}>
          Upload notice
        </button>
        <button
          type="button"
          className="ib"
          aria-label="Notifications"
          onClick={() => showToast("No notifications")}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M6 9a6 6 0 1 1 12 0c0 6 2 7 2 7H4s2-1 2-7M10 20a2 2 0 0 0 4 0" />
          </svg>
        </button>
        <NavLink className="prof" to="/settings" aria-label="Profile and settings">
          <div className="av">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21c1-5 15-5 16 0" />
            </svg>
          </div>
          <span>
            Reviewer
            <br />
            <small className="mono" style={{ color: "var(--mut)" }}>
              Not set
            </small>
          </span>
        </NavLink>
      </div>
    </header>
  );
}
