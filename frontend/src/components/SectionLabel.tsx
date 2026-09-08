interface SectionLabelProps {
  children: React.ReactNode;
  tone?: "light" | "dark";
  className?: string;
}

/** The recurring "■ LABEL" signature indicator used across the product. */
export default function SectionLabel({ children, tone = "light", className = "" }: SectionLabelProps) {
  return (
    <div
      className={`section-label ${tone === "dark" ? "text-vellum/70" : "text-carbon/70"} ${className}`}
    >
      {children}
    </div>
  );
}
