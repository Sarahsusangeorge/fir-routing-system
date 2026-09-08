import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import type { ExplanationToken } from "../types";

interface Segment {
  text: string;
  weight: number | null;
  key: string;
}

function buildSegments(text: string, tokens: ExplanationToken[]): Segment[] {
  const lower = text.toLowerCase();
  type Range = { start: number; end: number; weight: number };
  const ranges: Range[] = [];

  for (const t of tokens) {
    const needle = t.token.toLowerCase();
    if (!needle) continue;
    const idx = lower.indexOf(needle);
    if (idx === -1) continue;
    const overlaps = ranges.some((r) => idx < r.end && idx + needle.length > r.start);
    if (overlaps) continue;
    ranges.push({ start: idx, end: idx + needle.length, weight: t.weight });
  }

  ranges.sort((a, b) => a.start - b.start);

  const segments: Segment[] = [];
  let cursor = 0;
  ranges.forEach((r, i) => {
    if (r.start > cursor) {
      segments.push({ text: text.slice(cursor, r.start), weight: null, key: `plain-${i}` });
    }
    segments.push({ text: text.slice(r.start, r.end), weight: r.weight, key: `hl-${i}` });
    cursor = r.end;
  });
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), weight: null, key: "plain-end" });
  }
  return segments;
}

interface ExplainabilityViewerProps {
  complaintText: string;
  explanation: ExplanationToken[];
}

export default function ExplainabilityViewer({ complaintText, explanation }: ExplainabilityViewerProps) {
  const [hovered, setHovered] = useState<string | null>(null);
  const segments = useMemo(() => buildSegments(complaintText, explanation), [complaintText, explanation]);
  const maxWeight = useMemo(() => Math.max(0.01, ...explanation.map((t) => t.weight)), [explanation]);

  let highlightIndex = -1;

  return (
    <div className="bg-paper border border-line rounded-[24px] p-8">
      <p className="text-[17px] leading-[1.7] text-carbon">
        {segments.map((seg) => {
          if (seg.weight === null) {
            return <span key={seg.key}>{seg.text}</span>;
          }
          highlightIndex += 1;
          const idx = highlightIndex;
          const intensity = 0.16 + (seg.weight / maxWeight) * 0.5;
          const isHovered = hovered === seg.key;

          return (
            <span key={seg.key} className="relative inline-block">
              <motion.mark
                initial={{ backgroundColor: "rgba(50,45,42,0)" }}
                whileInView={{ backgroundColor: `rgba(50,45,42,${intensity})` }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: idx * 0.12, ease: [0.16, 1, 0.3, 1] }}
                tabIndex={0}
                role="button"
                aria-describedby={isHovered ? `tooltip-${seg.key}` : undefined}
                onMouseEnter={() => setHovered(seg.key)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(seg.key)}
                onBlur={() => setHovered(null)}
                className="rounded-[3px] px-0.5 text-carbon cursor-help focus:outline-none focus:ring-2 focus:ring-carbon/40"
              >
                {seg.text}
              </motion.mark>
              <AnimatePresence>
                {isHovered && (
                  <motion.span
                    id={`tooltip-${seg.key}`}
                    role="tooltip"
                    initial={{ opacity: 0, y: 4, x: "-50%" }}
                    animate={{ opacity: 1, y: 0, x: "-50%" }}
                    exit={{ opacity: 0, y: 4, x: "-50%" }}
                    transition={{ duration: 0.15 }}
                    className="absolute bottom-full left-1/2 mb-2 whitespace-nowrap px-3 py-1.5 rounded-[10px] bg-onyx text-vellum text-xs shadow-lg z-10"
                  >
                    Influence weight&nbsp;
                    <span className="font-medium tabular-nums">{seg.weight.toFixed(2)}</span>
                  </motion.span>
                )}
              </AnimatePresence>
            </span>
          );
        })}
      </p>

      <div className="flex items-center gap-3 mt-8 pt-6 border-t border-line">
        <span className="text-xs text-mercury whitespace-nowrap">Lower influence</span>
        <div
          className="flex-1 h-1.5 rounded-full"
          style={{ background: "linear-gradient(to right, rgba(50,45,42,0.1), rgba(50,45,42,0.7))" }}
          aria-hidden="true"
        />
        <span className="text-xs text-mercury whitespace-nowrap">Higher influence</span>
      </div>
    </div>
  );
}
