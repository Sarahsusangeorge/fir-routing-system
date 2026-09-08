import { motion } from "framer-motion";

const STEPS = ["Complaint", "Classification", "Priority", "Routing"];

interface RoutingFlowProps {
  destination: string;
}

export default function RoutingFlow({ destination }: RoutingFlowProps) {
  return (
    <div className="flex flex-col items-center" aria-hidden="true">
      {STEPS.map((step, i) => (
        <div key={step} className="flex flex-col items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.35, delay: i * 0.12 }}
            className="px-4 py-2 rounded-full border border-line bg-vellum/60 text-xs uppercase tracking-[0.08em] text-mercury"
          >
            {step}
          </motion.div>
          <motion.div
            className="w-px h-6 bg-line origin-top overflow-hidden relative"
            initial={{ scaleY: 0 }}
            whileInView={{ scaleY: 1 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.3, delay: i * 0.12 + 0.15 }}
          >
            <motion.span
              className="absolute inset-0 bg-carbon/40 motion-reduce:hidden"
              animate={{ y: ["-100%", "100%"] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: "linear", delay: i * 0.2 }}
            />
          </motion.div>
        </div>
      ))}
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true, margin: "-40px" }}
        transition={{ duration: 0.4, delay: STEPS.length * 0.12 }}
        className="px-5 py-2.5 rounded-full bg-carbon text-vellum text-sm font-medium"
      >
        {destination}
      </motion.div>
    </div>
  );
}
