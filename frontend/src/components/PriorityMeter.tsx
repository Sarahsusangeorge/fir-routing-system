import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import type { PriorityLevel } from "../types";

const COLOR: Record<PriorityLevel, string> = {
  High: "var(--color-priority-high)",
  Medium: "var(--color-priority-medium)",
  Low: "var(--color-priority-low)",
};

interface PriorityMeterProps {
  score: number; // 0–10
  level: PriorityLevel;
}

const SIZE = 148;
const STROKE = 8;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function PriorityMeter({ score, level }: PriorityMeterProps) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const fraction = Math.min(1, Math.max(0, score / 10));

  return (
    <div ref={ref} className="relative inline-flex items-center justify-center" style={{ width: SIZE, height: SIZE }}>
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="-rotate-90">
        <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="var(--color-line)" strokeWidth={STROKE} />
        <motion.circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={COLOR[level]}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          initial={{ strokeDashoffset: CIRCUMFERENCE }}
          animate={{ strokeDashoffset: inView ? CIRCUMFERENCE * (1 - fraction) : CIRCUMFERENCE }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[30px] leading-none font-light text-carbon tabular-nums">{score.toFixed(1)}</span>
        <span className="text-xs text-mercury mt-1">/ 10</span>
      </div>
    </div>
  );
}
