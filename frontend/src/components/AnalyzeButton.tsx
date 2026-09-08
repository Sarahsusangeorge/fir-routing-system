import { ArrowRight, Loader2 } from "lucide-react";

interface AnalyzeButtonProps {
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export default function AnalyzeButton({ onClick, loading, disabled }: AnalyzeButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="inline-flex items-center gap-2 px-7 py-3.5 rounded-full bg-carbon text-vellum text-[15px] font-medium hover:bg-onyx active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100"
    >
      {loading ? (
        <>
          <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />
          Analyzing complaint...
        </>
      ) : (
        <>
          Analyze complaint
          <ArrowRight className="w-4 h-4" strokeWidth={1.75} />
        </>
      )}
    </button>
  );
}
