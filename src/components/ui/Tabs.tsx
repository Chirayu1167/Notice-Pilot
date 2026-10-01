type TabsProps = {
  options: string[];
  selected?: string;
  onChange?: (option: string) => void;
  disabled?: boolean;
  countFor?: (option: string) => number;
};

export function Tabs({ options, selected, onChange, disabled = false, countFor }: TabsProps) {
  return (
    <div className="tabs" role="group" aria-label="Filter">
      {options.map((option) => {
        const active = selected === option;
        const count = countFor?.(option);
        return (
          <button
            key={option}
            type="button"
            aria-pressed={active}
            disabled={disabled || !onChange}
            onClick={() => onChange?.(option)}
          >
            {option}
            {count !== undefined ? (
              <>
                {" "}
                <span className="mono" style={{ color: "var(--mut)" }}>
                  {count}
                </span>
              </>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
