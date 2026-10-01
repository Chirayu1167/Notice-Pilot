import type { ReactNode } from "react";

type CardProps = {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
};

export function Card({ title, children, actions }: CardProps) {
  return (
    <section className="card">
      <div className="ch">
        <h2>{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}
