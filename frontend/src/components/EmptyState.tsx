import { motion } from "framer-motion";
import SectionLabel from "./SectionLabel";

export default function EmptyState() {
  return (
    <div className="flex flex-col items-center text-center py-20 px-6">
      <div className="relative w-12 h-12 mb-8 flex items-center justify-center">
        <motion.span
          className="absolute inset-0 rounded-full border border-carbon/15"
          animate={{ scale: [1, 1.6], opacity: [0.5, 0] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeOut" }}
        />
        <span className="w-2.5 h-2.5 bg-carbon rounded-full" aria-hidden="true" />
      </div>
      <SectionLabel className="justify-center mb-4">Ready</SectionLabel>
      <h2 className="text-[22px] font-normal text-carbon mb-2">NIVARA is ready to analyze a complaint.</h2>
      <p className="text-mercury text-base max-w-sm">Submit a complaint narrative to begin.</p>
    </div>
  );
}
