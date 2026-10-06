interface ModelBadgeProps {
  backend?: string | null;
  /** Omit the "Classifier:" prefix where a label already says it. */
  bare?: boolean;
}

/**
 * Names the classifier that produced a prediction, so an officer can tell a
 * DistilBERT result from the keyword fallback without reading server logs.
 */
export default function ModelBadge({ backend, bare = false }: ModelBadgeProps) {
  if (!backend) return null;
  const isModel = backend === "distilbert";
  const degraded = backend.includes("unavailable");
  const label = isModel ? "DistilBERT model" : degraded ? "Keyword fallback (model unavailable)" : "Keyword rules (prototype)";
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs border ${
        degraded ? "border-[color:var(--color-priority-high)] text-carbon" : "border-line text-mercury"
      }`}
      title={`Classifier: ${backend}`}
    >
      {bare ? label : `Classifier: ${label}`}
    </span>
  );
}
