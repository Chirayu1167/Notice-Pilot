import { useEffect, useRef, type ReactNode } from "react";

type ModalProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
  closeOnEscape?: boolean;
};

export function Modal({ title, subtitle, children, actions, onClose, closeOnEscape = true }: ModalProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && closeOnEscape) onClose();
    };
    document.addEventListener("keydown", onKey);
    ref.current?.querySelector<HTMLElement>("button, input, select, [tabindex]")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, closeOnEscape]);

  return (
    <div className="modal" role="presentation">
      <div
        className="md"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
      >
        <div className="ch">
          <div>
            <h2 className="h2s">{title}</h2>
            {subtitle ? <span className="sub">{subtitle}</span> : null}
          </div>
        </div>
        {children}
        {actions ? (
          <div className="ch" style={{ borderTop: "1px solid var(--bd)", borderBottom: 0, justifyContent: "flex-end" }}>
            {actions}
          </div>
        ) : null}
      </div>
    </div>
  );
}
