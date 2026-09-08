import type { PriorityLevel } from "../types";

const STYLES: Record<PriorityLevel, string> = {
  High: "text-[color:var(--color-priority-high)] bg-[color:var(--color-priority-high-bg)]",
  Medium: "text-[color:var(--color-priority-medium)] bg-[color:var(--color-priority-medium-bg)]",
  Low: "text-[color:var(--color-priority-low)] bg-[color:var(--color-priority-low-bg)]",
};

const DOT: Record<PriorityLevel, string> = {
  High: "bg-[color:var(--color-priority-high)]",
  Medium: "bg-[color:var(--color-priority-medium)]",
  Low: "bg-[color:var(--color-priority-low)]",
};

interface StatusBadgeProps {
  level: PriorityLevel;
  className?: string;
}

export default function StatusBadge({ level, className = "" }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium tracking-wide ${STYLES[level]} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${DOT[level]}`} aria-hidden="true" />
      {level}
    </span>
  );
}
