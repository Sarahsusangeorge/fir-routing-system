import type { ComplaintStatus } from "../types";

const STYLES: Record<ComplaintStatus, string> = {
  New: "bg-carbon text-vellum",
  "Under Review": "bg-paper text-carbon border border-carbon/25",
  Registered: "bg-paper text-carbon border border-carbon/25",
  "Under Investigation": "text-[color:var(--color-priority-medium)] bg-[color:var(--color-priority-medium-bg)]",
  "Charge Sheet Filed": "text-[color:var(--color-priority-low)] bg-[color:var(--color-priority-low-bg)]",
  Closed: "bg-mercury-light/60 text-carbon/70",
  "Not Registered": "bg-mercury-light/60 text-carbon/70",
};

interface ComplaintStatusBadgeProps {
  status: ComplaintStatus;
  className?: string;
}

/** Where a case is in its lifecycle. Distinct from StatusBadge, which shows priority. */
export default function ComplaintStatusBadge({ status, className = "" }: ComplaintStatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap ${STYLES[status] ?? STYLES.New} ${className}`}
    >
      {status}
    </span>
  );
}
