import { AlertCircle } from "lucide-react";

interface ErrorStateProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center text-center gap-4 py-14 px-6 bg-[color:var(--color-priority-high-bg)]/60 border border-[color:var(--color-priority-high)]/20 rounded-[24px]"
    >
      <AlertCircle className="w-6 h-6 text-[color:var(--color-priority-high)]" strokeWidth={1.5} aria-hidden="true" />
      <div>
        <h2 className="text-base font-medium text-carbon mb-1">{title}</h2>
        <p className="text-sm text-mercury max-w-sm">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 px-5 py-2 rounded-full text-sm font-medium bg-carbon text-vellum hover:bg-onyx transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  );
}
