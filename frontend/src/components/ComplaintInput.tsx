import { Camera } from "lucide-react";
import { useId } from "react";

interface ComplaintInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: string | null;
  maxLength?: number;
  onScanClick?: () => void;
}

export default function ComplaintInput({ value, onChange, disabled, error, maxLength = 2000, onScanClick }: ComplaintInputProps) {
  const id = useId();

  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <label htmlFor={id} className="text-[15px] font-medium text-carbon">
          Submit complaint
        </label>
        <span className="text-xs text-mercury tabular-nums" aria-live="polite">
          {value.length} / {maxLength}
        </span>
      </div>
      <div className="flex items-start justify-between gap-4 mb-4">
        <p className="text-sm text-mercury">Enter or paste a complaint narrative to begin analysis.</p>
        {onScanClick && (
          <button
            type="button"
            onClick={onScanClick}
            disabled={disabled}
            className="shrink-0 inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full border border-line text-sm text-carbon hover:bg-vellum/60 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Camera className="w-4 h-4" strokeWidth={1.75} />
            Scan document
          </button>
        )}
      </div>

      <textarea
        id={id}
        value={value}
        disabled={disabled}
        maxLength={maxLength}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Enter complaint text..."
        rows={7}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`w-full resize-none rounded-[24px] border bg-vellum/40 px-5 py-4 text-[16px] leading-[1.5] text-carbon placeholder:text-mercury focus:outline-none focus:ring-2 focus:ring-carbon/30 focus:border-carbon/40 transition-colors disabled:opacity-60 ${
          error ? "border-[color:var(--color-priority-high)]/50" : "border-line"
        }`}
      />

      {error && (
        <p id={`${id}-error`} role="alert" className="mt-2 text-sm text-[color:var(--color-priority-high)]">
          {error}
        </p>
      )}
    </div>
  );
}
