import { motion } from "framer-motion";
import type { Priority } from "../types";
import PriorityMeter from "./PriorityMeter";
import StatusBadge from "./StatusBadge";

interface PriorityCardProps {
  priority: Priority;
}

export default function PriorityCard({ priority }: PriorityCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="bg-paper border border-line rounded-[24px] p-8 flex flex-col sm:flex-row items-center gap-8"
    >
      <PriorityMeter score={priority.score} level={priority.level} />
      <div className="text-center sm:text-left">
        <span className="text-xs uppercase tracking-[0.1em] text-mercury">Priority</span>
        <div className="mt-2 mb-3">
          <StatusBadge level={priority.level} />
        </div>
        <p className="text-sm text-mercury max-w-xs">{priority.basis ?? "Rule-based priority assessment"}</p>
      </div>
    </motion.div>
  );
}
