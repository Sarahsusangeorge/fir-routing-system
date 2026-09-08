import { motion } from "framer-motion";
import type { Complaint } from "../types";
import StatusBadge from "./StatusBadge";

interface HistoryTableProps {
  complaints: Complaint[];
  onSelect: (complaint: Complaint) => void;
  loading?: boolean;
}

function truncate(text: string, max = 72) {
  return text.length > max ? `${text.slice(0, max).trim()}…` : text;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
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

export default function HistoryTable({ complaints, onSelect, loading }: HistoryTableProps) {
  if (loading) return <SkeletonRows />;

  if (complaints.length === 0) {
    return (
      <div className="py-16 text-center text-mercury text-sm">
        No complaints match your current filters.
      </div>
    );
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-[0.08em] text-mercury">
              <th className="py-3 pr-4 font-medium">ID</th>
              <th className="py-3 pr-4 font-medium">Complaint</th>
              <th className="py-3 pr-4 font-medium">Date</th>
              <th className="py-3 pr-4 font-medium">Sections</th>
              <th className="py-3 pr-4 font-medium">Priority</th>
              <th className="py-3 pr-4 font-medium">Score</th>
              <th className="py-3 pr-4 font-medium">Routed unit</th>
              <th className="py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {complaints.map((c, i) => (
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
                role="button"
                aria-label={`View details for complaint ${c.complaint_id}`}
                className="border-b border-line last:border-0 cursor-pointer hover:bg-vellum/50 focus-visible:bg-vellum/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-carbon/30 focus-visible:ring-inset"
              >
                <td className="py-4 pr-4 text-sm text-mercury tabular-nums">#{c.complaint_id}</td>
                <td className="py-4 pr-4 text-sm text-carbon max-w-[280px]">{truncate(c.complaint_text)}</td>
                <td className="py-4 pr-4 text-sm text-mercury whitespace-nowrap">{formatDate(c.received_at)}</td>
                <td className="py-4 pr-4">
                  <div className="flex flex-wrap gap-1.5">
                    {c.sections.map((s) => (
                      <span key={s.code} className="px-2 py-0.5 rounded-full bg-vellum text-xs text-carbon/80 whitespace-nowrap">
                        {s.code}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="py-4 pr-4">
                  <StatusBadge level={c.priority.level} />
                </td>
                <td className="py-4 pr-4 text-sm text-carbon tabular-nums">{c.priority.score.toFixed(1)}</td>
                <td className="py-4 pr-4 text-sm text-mercury whitespace-nowrap">{c.routing.unit}</td>
                <td className="py-4 text-sm text-mercury whitespace-nowrap">Reviewed</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden flex flex-col divide-y divide-line">
        {complaints.map((c, i) => (
          <motion.button
            key={c.complaint_id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: Math.min(i, 8) * 0.03 }}
            onClick={() => onSelect(c)}
            className="text-left py-4 active:bg-vellum/50 transition-colors -mx-4 px-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-mercury tabular-nums">#{c.complaint_id}</span>
              <StatusBadge level={c.priority.level} />
            </div>
            <p className="text-sm text-carbon mb-3">{truncate(c.complaint_text, 100)}</p>
            <div className="flex items-center justify-between text-xs text-mercury">
              <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
                {c.sections.map((s) => (
                  <span key={s.code} className="px-2 py-0.5 rounded-full bg-vellum text-carbon/80 whitespace-nowrap">
                    {s.code}
                  </span>
                ))}
              </div>
              <span className="whitespace-nowrap pl-2">{formatDate(c.received_at)}</span>
            </div>
          </motion.button>
        ))}
      </div>
    </>
  );
}
