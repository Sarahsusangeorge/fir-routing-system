import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import type { Priority } from "../types";
import PriorityMeter from "./PriorityMeter";
import StatusBadge from "./StatusBadge";

interface PriorityCardProps {
  priority: Priority;
}

export default function PriorityCard({ priority }: PriorityCardProps) {
  const reasons = priority.review_reasons ?? [];
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="bg-paper border border-line rounded-[24px] p-8"
    >
      <div className="flex flex-col sm:flex-row items-center gap-8">
        <PriorityMeter score={priority.score} level={priority.level} />
        <div className="text-center sm:text-left">
          <span className="text-xs uppercase tracking-[0.1em] text-mercury">Suggested priority</span>
          <div className="mt-2 mb-3">
            <StatusBadge level={priority.level} />
          </div>
          <p className="text-sm text-mercury max-w-xs">{priority.basis ?? "Rule-based priority assessment"}</p>
          <p className="text-xs text-mercury mt-2 max-w-xs">
            A recommendation from the triage rules, not a legal finding. The officer decides.
          </p>
        </div>
      </div>
      {priority.review_required && reasons.length > 0 && (
        <div
          role="note"
          aria-label="Officer review needed"
          className="mt-6 rounded-[16px] border border-[color:var(--color-priority-medium)]/40 bg-[color:var(--color-priority-medium-bg)] px-5 py-4"
        >
          <p className="flex items-center gap-2 text-sm font-medium text-carbon">
            <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
            Officer review needed
          </p>
          <ul className="mt-2 flex flex-col gap-1.5 text-sm text-carbon/90 leading-[1.5] list-disc pl-5">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </motion.div>
  );
}
