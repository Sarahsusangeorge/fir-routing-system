import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import AnalysisHeader from "../components/AnalysisHeader";
import AnalysisProgress from "../components/AnalysisProgress";
import AnalyzeButton from "../components/AnalyzeButton";
import ArchitecturalMark from "../components/ArchitecturalMark";
import ComplaintInput from "../components/ComplaintInput";
import ComplaintScanner from "../components/ComplaintScanner";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import ExplainabilityViewer from "../components/ExplainabilityViewer";
import PriorityCard from "../components/PriorityCard";
import RoutingCard from "../components/RoutingCard";
import SectionCard from "../components/SectionCard";
import SectionLabel from "../components/SectionLabel";
import { classifyComplaint, ClassificationError } from "../services/api";
import type { Complaint } from "../types";

type ViewState = "idle" | "analyzing" | "result" | "error";

export default function AnalyzePage() {
  const [text, setText] = useState("");
  const [state, setState] = useState<ViewState>("idle");
  const [result, setResult] = useState<Complaint | null>(null);
  const [pending, setPending] = useState<Complaint | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiErrorMessage, setApiErrorMessage] = useState<string>("");
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scanNotice, setScanNotice] = useState<string | null>(null);

  const handleScanExtracted = (extractedText: string, confidence?: number) => {
    setText(extractedText);
    setValidationError(null);
    setScanNotice(
      typeof confidence === "number"
        ? `Extracted from photo — review before analyzing (${Math.round(confidence)}% OCR confidence).`
        : "Extracted from photo — review before analyzing."
    );
  };

  const handleTextChange = (value: string) => {
    setText(value);
    if (scanNotice) setScanNotice(null);
  };

  const runAnalysis = async () => {
    setPending(null);
    setState("analyzing");
    try {
      // The request starts straight away; the progress animation runs alongside
      // it and only reports completion once this has resolved.
      setPending(await classifyComplaint(text));
    } catch (err) {
      setApiErrorMessage(
        err instanceof ClassificationError ? err.message : "The classification service could not be reached."
      );
      setState("error");
    }
  };

  const handleAnalyze = () => {
    if (text.trim().length < 15) {
      setValidationError(
        text.trim() ? "Describe the incident in a little more detail (at least 15 characters)." : "Enter a complaint narrative before analysis."
      );
      return;
    }
    setValidationError(null);
    void runAnalysis();
  };

  const handleProgressComplete = () => {
    setResult(pending);
    setState("result");
    // Move keyboard and screen-reader focus to the result that just appeared.
    requestAnimationFrame(() => resultRef.current?.focus());
  };

  const handleRetry = () => {
    void runAnalysis();
  };

  const handleNewComplaint = () => {
    setText("");
    setResult(null);
    setState("idle");
  };

  return (
    <div className="container-page pt-32 pb-24">
      <div className="relative">
        <ArchitecturalMark className="hidden lg:block absolute -top-6 right-0 w-64 h-32 text-carbon/[0.05]" />
        <SectionLabel className="mb-6">AI complaint intelligence</SectionLabel>
        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="text-[38px] md:text-[52px] font-light leading-[1.05] tracking-[0.01em] text-carbon max-w-3xl"
        >
          Turn complaint narratives into actionable intelligence.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-base text-mercury mt-6 max-w-xl leading-[1.5]"
        >
          NIVARA analyzes unstructured complaints, identifies relevant legal sections, assesses priority, and
          recommends the appropriate destination.
        </motion.p>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="bg-paper border border-line rounded-[24px] p-6 md:p-10 mt-14"
      >
        {state === "analyzing" ? (
          <AnalysisProgress done={pending !== null} onComplete={handleProgressComplete} />
        ) : (
          <>
            <ComplaintInput
              value={text}
              onChange={handleTextChange}
              error={validationError}
              onScanClick={() => setScannerOpen(true)}
            />
            {scanNotice && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-xs text-mercury mt-3"
              >
                {scanNotice}
              </motion.p>
            )}
            <div className="flex items-center justify-between mt-6 flex-wrap gap-4">
              {result ? (
                <button
                  onClick={handleNewComplaint}
                  className="text-sm text-mercury hover:text-carbon transition-colors underline underline-offset-4"
                >
                  Start a new complaint
                </button>
              ) : (
                <span />
              )}
              <AnalyzeButton onClick={handleAnalyze} />
            </div>
          </>
        )}
      </motion.div>

      <div className="mt-16">
        <AnimatePresence mode="wait">
          {state === "idle" && !result && (
            <motion.div key="empty" exit={{ opacity: 0 }}>
              <EmptyState />
            </motion.div>
          )}

          {state === "error" && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <ErrorState
                title="Unable to analyze complaint"
                message={apiErrorMessage}
                onRetry={handleRetry}
              />
            </motion.div>
          )}

          {state === "result" && result && (
            <motion.div key="result" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-16">
              <div ref={resultRef} tabIndex={-1} aria-label={`Analysis of complaint ${result.complaint_id}`} className="focus:outline-none">
                {result.duplicate && (
                  <p className="text-sm text-carbon bg-paper border border-line rounded-[16px] px-5 py-4 mb-6 max-w-2xl">
                    This complaint was already filed a few minutes ago, so no new case was created. Below is the
                    existing case #{result.complaint_id}.
                  </p>
                )}
                {result.assignment?.officer_name ? (
                  <p className="text-sm text-mercury mb-6">
                    Allocated to <span className="text-carbon">{result.assignment.officer_name}</span> in{" "}
                    {result.routing.unit}.{" "}
                    <Link to={`/cases/${result.complaint_id}`} className="underline underline-offset-4 hover:text-carbon">
                      Open the case
                    </Link>
                  </p>
                ) : (
                  <p className="text-sm text-mercury mb-6">
                    Saved, but no officer in {result.routing.unit} is available yet; the case is waiting in the
                    unassigned queue.
                  </p>
                )}

                <AnalysisHeader
                  complaintId={result.complaint_id}
                  receivedAt={result.received_at}
                  modelBackend={result.model_backend}
                />
              </div>

              <div>
                <PriorityCard priority={result.priority} />
              </div>

              <div>
                <SectionLabel className="mb-3">Legal classification</SectionLabel>
                <h2 className="text-[26px] font-normal text-carbon mb-6">Detected sections</h2>
                <div className="grid sm:grid-cols-2 gap-4">
                  {result.sections.map((s, i) => (
                    <SectionCard key={s.code} section={s} index={i} />
                  ))}
                </div>
              </div>

              <div>
                <SectionLabel className="mb-3">Intelligent routing</SectionLabel>
                <h2 className="text-[26px] font-normal text-carbon mb-6">Recommended destination</h2>
                <RoutingCard routing={result.routing} />
              </div>

              <div>
                <SectionLabel className="mb-3">Model explanation</SectionLabel>
                <h2 className="text-[26px] font-normal text-carbon mb-3">Why did NIVARA classify this complaint?</h2>
                <p className="text-sm text-mercury mb-6 max-w-xl">
                  Highlighted tokens indicate the relative influence returned by the model's explainability output.
                </p>
                <ExplainabilityViewer complaintText={result.complaint_text} explanation={result.explanation} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <ComplaintScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onExtracted={handleScanExtracted}
      />
    </div>
  );
}
