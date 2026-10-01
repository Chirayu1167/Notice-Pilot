import type { ReactNode } from "react";

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state" role="status">
      <div className="spin" />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state" role="alert">
      {message}
    </div>
  );
}

export function SuccessState({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}

export function NeedsReviewState({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}
