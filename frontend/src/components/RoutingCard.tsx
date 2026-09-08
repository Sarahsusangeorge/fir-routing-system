import { motion } from "framer-motion";
import type { Routing } from "../types";
import RoutingFlow from "./RoutingFlow";

interface RoutingCardProps {
  routing: Routing;
}

export default function RoutingCard({ routing }: RoutingCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="bg-paper border border-line rounded-[24px] p-8 grid md:grid-cols-[1fr_auto] gap-10 items-center"
    >
      <div>
        <span className="text-xs uppercase tracking-[0.1em] text-mercury">Recommended destination</span>
        <h3 className="text-[28px] font-light text-carbon mt-2 mb-5">{routing.unit}</h3>
        <span className="text-xs uppercase tracking-[0.1em] text-mercury">Routing rationale</span>
        <p className="text-[15px] text-carbon/80 mt-2 leading-[1.5]">{routing.reason}</p>
        <p className="text-xs text-mercury mt-5">Routing is determined by rule-based section mapping, not manual judgment.</p>
      </div>
      <RoutingFlow destination={routing.unit} />
    </motion.div>
  );
}
