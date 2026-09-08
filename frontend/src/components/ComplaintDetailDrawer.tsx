import { AnimatePresence, motion } from "framer-motion";
import { Info, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { isDemoMode } from "../services/api";
import type { Complaint } from "../types";
import ExplainabilityViewer from "./ExplainabilityViewer";
import PriorityCard from "./PriorityCard";
import RoutingCard from "./RoutingCard";
import SectionCard from "./SectionCard";
import SectionLabel from "./SectionLabel";

interface ComplaintDetailDrawerProps {
  complaint: Complaint | null;
  onClose: () => void;
}

export default function ComplaintDetailDrawer({ complaint, onClose }: ComplaintDetailDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!complaint) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [complaint, onClose]);

  return (
    <AnimatePresence>
      {complaint && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="fixed inset-0 bg-onyx/40 backdrop-blur-[2px] z-[60]"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="drawer-title"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-0 right-0 h-full w-full sm:w-[560px] bg-vellum z-[70] overflow-y-auto"
          >
            <div className="sticky top-0 bg-vellum/90 backdrop-blur-md border-b border-line flex items-center justify-between px-6 py-4 z-10">
              <div>
                <SectionLabel>Complaint detail</SectionLabel>
                <h2 id="drawer-title" className="text-lg font-medium text-carbon mt-1">
                  Complaint #{complaint.complaint_id}
                </h2>
              </div>
              <button
                ref={closeRef}
                onClick={onClose}
                aria-label="Close detail panel"
                className="p-3 -mr-1 rounded-full hover:bg-line/60 transition-colors"
              >
                <X className="w-5 h-5 text-carbon" strokeWidth={1.75} />
              </button>
            </div>

            {isDemoMode() && (
              <p className="flex items-start gap-2 text-xs text-mercury px-6 pt-6">
                <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
                Demo mode — this is a synthetic record generated for demonstration only, not a real complaint.
              </p>
            )}

            <div className="px-6 py-8 flex flex-col gap-8">
              <div>
                <span className="text-xs uppercase tracking-[0.1em] text-mercury">Received</span>
                <p className="text-sm text-carbon mt-1">
                  {new Date(complaint.received_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </p>
              </div>

              <div>
                <span className="text-xs uppercase tracking-[0.1em] text-mercury">Complaint narrative</span>
                <p className="text-[15px] text-carbon/90 leading-[1.6] mt-2">{complaint.complaint_text}</p>
              </div>

              <PriorityCard priority={complaint.priority} />

              <div>
                <SectionLabel className="mb-4">Legal classification</SectionLabel>
                <div className="flex flex-col gap-4">
                  {complaint.sections.map((s, i) => (
                    <SectionCard key={s.code} section={s} index={i} />
                  ))}
                </div>
              </div>

              <div>
                <SectionLabel className="mb-4">Intelligent routing</SectionLabel>
                <RoutingCard routing={complaint.routing} />
              </div>

              <div>
                <SectionLabel className="mb-4">Model explanation</SectionLabel>
                <ExplainabilityViewer complaintText={complaint.complaint_text} explanation={complaint.explanation} />
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
