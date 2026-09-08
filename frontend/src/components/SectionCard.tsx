import { motion } from "framer-motion";
import type { Section } from "../types";
import ConfidenceBar from "./ConfidenceBar";

interface SectionCardProps {
  section: Section;
  index: number;
}

export default function SectionCard({ section, index }: SectionCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.45, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
      className="bg-paper border border-line rounded-[24px] p-6"
    >
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <span className="text-[28px] font-light text-carbon leading-none">{section.code}</span>
          <p className="text-[15px] text-mercury mt-1">{section.title}</p>
        </div>
      </div>
      <ConfidenceBar confidence={section.confidence} delay={index * 0.1} />
    </motion.div>
  );
}
