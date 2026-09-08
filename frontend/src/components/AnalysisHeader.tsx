import { motion } from "framer-motion";
import SectionLabel from "./SectionLabel";

interface AnalysisHeaderProps {
  complaintId: number;
  receivedAt: string;
}

export default function AnalysisHeader({ complaintId, receivedAt }: AnalysisHeaderProps) {
  const formatted = new Date(receivedAt).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-wrap items-center justify-between gap-3 mb-6"
    >
      <SectionLabel>Analysis complete</SectionLabel>
      <div className="flex items-center gap-3 text-sm text-mercury">
        <span className="font-medium text-carbon">Complaint #{complaintId}</span>
        <span aria-hidden="true">·</span>
        <span>{formatted}</span>
      </div>
    </motion.div>
  );
}
