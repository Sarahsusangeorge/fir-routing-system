import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const STAGES = [
  "Reading complaint",
  "Identifying legal signals",
  "Classifying sections",
  "Calculating priority",
  "Determining routing",
  "Analysis complete",
];

const STAGE_DURATION = 320; // ms per stage

interface AnalysisProgressProps {
  onComplete: () => void;
}

export default function AnalysisProgress({ onComplete }: AnalysisProgressProps) {
  const [stageIndex, setStageIndex] = useState(0);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = prefersReduced ? 60 : STAGE_DURATION;

    if (stageIndex >= STAGES.length - 1) {
      const finish = setTimeout(() => onCompleteRef.current(), duration + 200);
      return () => clearTimeout(finish);
    }
    const t = setTimeout(() => setStageIndex((i) => i + 1), duration);
    return () => clearTimeout(t);
  }, [stageIndex]);

  const progress = ((stageIndex + 1) / STAGES.length) * 100;

  return (
    <div className="relative overflow-hidden bg-paper border border-line rounded-[24px] px-8 py-16 flex flex-col items-center justify-center text-center">
      <div
        className="absolute inset-x-0 top-0 h-px bg-line overflow-hidden"
        aria-hidden="true"
      >
        <motion.div
          className="h-full bg-carbon"
          initial={{ width: "0%" }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.3, ease: "easeOut" }}
        />
      </div>

      <motion.span
        className="absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-carbon/[0.03] to-transparent pointer-events-none motion-reduce:hidden"
        animate={{ top: ["-10%", "110%"] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "linear" }}
        aria-hidden="true"
      />

      <div className="relative h-8 mb-2" role="status" aria-live="polite">
        <AnimatePresence mode="wait">
          <motion.p
            key={stageIndex}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="text-xs uppercase tracking-[0.14em] text-carbon/70"
          >
            {STAGES[stageIndex]}
          </motion.p>
        </AnimatePresence>
      </div>

      <div className="flex items-center gap-1.5 mt-4" aria-hidden="true">
        {STAGES.map((_, i) => (
          <span
            key={i}
            className={`h-1 rounded-full transition-all duration-300 ${
              i <= stageIndex ? "w-6 bg-carbon" : "w-1.5 bg-line"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
