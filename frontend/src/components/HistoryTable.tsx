import { motion } from "framer-motion";
import type { Complaint } from "../types";
import { formatDate, isPast } from "../utils/format";
import ComplaintStatusBadge from "./ComplaintStatusBadge";
import StatusBadge from "./StatusBadge";

interface HistoryTableProps {
  complaints: Complaint[];
  onSelect: (complaint: Complaint) => void;
  loading?: boolean;
  /** Show the assigned officer (administrator view). */
  showOfficer?: boolean;
  emptyMessage?: string;
}

function truncate(text: string, max = 72) {
  return text.length > max ? `${text.slice(0, max).trim()}…` : text;
}

/** A short reason this case needs attention now, if any. */
function attention(c: Complaint): string | null {
  const status = c.status ?? "New";
  const signatureOpen = c.source === "citizen" && !c.review?.signature_confirmed_at && (status === "New" || status === "Under Review");
  if (signatureOpen && isPast(c.review?.signature_due_at)) return "Signature overdue";
  if (status === "New") return "Not yet reviewed";
  if (signatureOpen) return "Awaiting signature";
  return null;
}

function SkeletonRows() {
  return (
    <div className="divide-y divide-line">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 py-5 animate-pulse">
          <div className="h-4 w-8 bg-line rounded" />
          <div className="h-4 flex-1 bg-line rounded" />
          <div className="h-4 w-20 bg-line rounded hidden md:block" />
          <div className="h-4 w-16 bg-line rounded hidden md:block" />
          <div className="h-6 w-20 bg-line rounded-full" />
        </div>
      ))}
    </div>
  );
}

export default function HistoryTable({
  complaints,
  onSelect,
  loading,
  showOfficer,
  emptyMessage = "No cases match your current filters.",
}: HistoryTableProps) {
  if (loading) return <SkeletonRows />;

  if (complaints.length === 0) {
    return <div className="py-16 text-center text-mercury text-sm">{emptyMessage}</div>;
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-[0.08em] text-mercury">
              <th className="py-3 pr-4 font-medium">Case</th>
              <th className="py-3 pr-4 font-medium">Complaint</th>
              <th className="py-3 pr-4 font-medium">Priority</th>
              <th className="py-3 pr-4 font-medium">Status</th>
              <th className="py-3 pr-4 font-medium">Unit</th>
              {showOfficer && <th className="py-3 pr-4 font-medium">Officer</th>}
              <th className="py-3 font-medium">Received</th>
            </tr>
          </thead>
          <tbody>
            {complaints.map((c, i) => {
              const flag = attention(c);
              return (
                <motion.tr
                  key={c.complaint_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3, delay: Math.min(i, 8) * 0.03 }}
                  onClick={() => onSelect(c)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(c);
                    }
                  }}
                  tabIndex={0}
                  role="link"
                  aria-label={`Open case ${c.complaint_id}`}
                  className="border-b border-line last:border-0 cursor-pointer hover:bg-vellum/50 focus-visible:bg-vellum/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-carbon/30 focus-visible:ring-inset"
                >
                  <td className="py-4 pr-4 text-sm text-carbon tabular-nums align-top">#{c.complaint_id}</td>
                  <td className="py-4 pr-4 text-sm text-carbon max-w-[300px] align-top">
                    {truncate(c.complaint_text)}
                    {flag && (
                      <span className="block text-xs text-[color:var(--color-priority-high)] mt-1">{flag}</span>
                    )}
                  </td>
                  <td className="py-4 pr-4 align-top">
                    <StatusBadge level={c.priority.level} />
                  </td>
                  <td className="py-4 pr-4 align-top">
                    <ComplaintStatusBadge status={c.status ?? "New"} />
                  </td>
                  <td className="py-4 pr-4 text-sm text-mercury align-top">{c.routing.unit}</td>
                  {showOfficer && (
                    <td className="py-4 pr-4 text-sm align-top">
                      {c.assignment?.officer_name ?? (
                        <span className="text-[color:var(--color-priority-high)]">Unassigned</span>
                      )}
                    </td>
                  )}
                  <td className="py-4 text-sm text-mercury whitespace-nowrap align-top">{formatDate(c.received_at)}</td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden flex flex-col divide-y divide-line">
        {complaints.map((c, i) => {
          const flag = attention(c);
          return (
            <motion.button
              key={c.complaint_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: Math.min(i, 8) * 0.03 }}
              onClick={() => onSelect(c)}
              className="text-left py-4 active:bg-vellum/50 transition-colors -mx-4 px-4"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="flex items-center gap-2 min-w-0">
                  <span className="text-sm text-carbon tabular-nums">#{c.complaint_id}</span>
                  <ComplaintStatusBadge status={c.status ?? "New"} />
                </span>
                <StatusBadge level={c.priority.level} />
              </div>
              <p className="text-sm text-carbon mb-2">{truncate(c.complaint_text, 100)}</p>
              {flag && <p className="text-xs text-[color:var(--color-priority-high)] mb-2">{flag}</p>}
              <div className="flex items-center justify-between gap-3 text-xs text-mercury">
                <span className="truncate">
                  {showOfficer ? c.assignment?.officer_name ?? "Unassigned" : c.routing.unit}
                </span>
                <span className="whitespace-nowrap">{formatDate(c.received_at)}</span>
              </div>
            </motion.button>
          );
        })}
      </div>
    </>
  );
}
