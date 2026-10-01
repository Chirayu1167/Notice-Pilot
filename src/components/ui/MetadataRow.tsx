const DASH = <span className="mono" style={{ color: "var(--mut)" }}>–</span>;

export function MetadataRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="mr">
      <span>{label}</span>
      {value === undefined || value === null || value === "" ? DASH : <span className="mono">{value}</span>}
    </div>
  );
}
