import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import { useCountUp } from "../hooks/useCountUp";

interface StatCardProps {
  label: string;
  value: number;
  accent?: "high" | "medium" | "low" | "neutral";
  delay?: number;
}

const ACCENT_DOT: Record<NonNullable<StatCardProps["accent"]>, string> = {
  high: "bg-[color:var(--color-priority-high)]",
  medium: "bg-[color:var(--color-priority-medium)]",
  low: "bg-[color:var(--color-priority-low)]",
  neutral: "bg-carbon",
};

export default function StatCard({ label, value, accent = "neutral", delay = 0 }: StatCardProps) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const count = useCountUp(value, inView);

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 16 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
      className="bg-paper border border-line rounded-[24px] p-6 md:p-8"
    >
      <div className="flex items-center gap-2 mb-4">
        <span className={`w-1.5 h-1.5 rounded-full ${ACCENT_DOT[accent]}`} aria-hidden="true" />
        <span className="text-xs uppercase tracking-[0.1em] text-mercury">{label}</span>
      </div>
      <span className="text-[40px] leading-none font-light text-carbon tabular-nums">
        {Math.round(count)}
      </span>
    </motion.div>
  );
}
