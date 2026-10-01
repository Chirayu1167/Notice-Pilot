import type { ReactNode } from "react";

type PageHeaderProps = {
  crumb: string;
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
};

export function PageHeader({ crumb, title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="ph">
      <div>
        <div className="crumb lbl">{crumb}</div>
        <h1>{title}</h1>
        {subtitle ? <p className="sub">{subtitle}</p> : null}
      </div>
      {actions ? <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>{actions}</div> : null}
    </div>
  );
}
