import { motion, useInView } from "framer-motion";
import { useRef } from "react";

interface ConfidenceBarProps {
  confidence: number; // 0–1
  delay?: number;
}

export default function ConfidenceBar({ confidence, delay = 0 }: ConfidenceBarProps) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const percent = Math.round(confidence * 100);

  return (
    <div ref={ref}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs uppercase tracking-[0.1em] text-mercury">Confidence</span>
        <span className="text-sm font-medium text-carbon tabular-nums">{percent}%</span>
      </div>
      <div
        className="h-1.5 w-full bg-vellum rounded-full overflow-hidden"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Classification confidence"
      >
        <motion.div
          className="h-full bg-carbon rounded-full"
          initial={{ width: "0%" }}
          animate={{ width: inView ? `${percent}%` : "0%" }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay }}
        />
      </div>
    </div>
  );
}
