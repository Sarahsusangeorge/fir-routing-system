interface ArchitecturalMarkProps {
  className?: string;
}

/**
 * Abstract line-art motif inspired by courthouse colonnades — used as a
 * quiet secondary visual. Deliberately non-literal (no gavels, scales,
 * or courtroom photography) so the product interface stays the focus.
 */
export default function ArchitecturalMark({ className = "" }: ArchitecturalMarkProps) {
  return (
    <svg
      viewBox="0 0 480 240"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <line x1="0" y1="220" x2="480" y2="220" stroke="currentColor" strokeWidth="1" />
      {Array.from({ length: 9 }).map((_, i) => {
        const x = 20 + i * 55;
        return <line key={i} x1={x} y1="60" x2={x} y2="220" stroke="currentColor" strokeWidth="1" />;
      })}
      <line x1="0" y1="60" x2="480" y2="60" stroke="currentColor" strokeWidth="1" />
      <path d="M -10 60 L 240 8 L 490 60" fill="none" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}
