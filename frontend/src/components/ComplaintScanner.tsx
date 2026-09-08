import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, Camera, ImagePlus, RotateCcw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { scanDocument, ScanError } from "../services/ocr";
import SectionLabel from "./SectionLabel";

type ScannerState = "choose" | "preview" | "processing" | "error";

interface ComplaintScannerProps {
  open: boolean;
  onClose: () => void;
  /** Called with the reviewed-and-editable extracted text once OCR succeeds. */
  onExtracted: (text: string, confidence?: number) => void;
}

export default function ComplaintScanner({ open, onClose, onExtracted }: ComplaintScannerProps) {
  const [state, setState] = useState<ScannerState>("choose");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");

  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const reset = () => {
    setState("choose");
    setFile(null);
    setProgress(0);
    setErrorMessage("");
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
  };

  useEffect(() => {
    if (!open) return;
    reset();
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFileSelected = (selected: File | undefined) => {
    if (!selected) return;
    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
    setState("preview");
  };

  const handleConfirm = async () => {
    if (!file) return;
    setState("processing");
    setProgress(0);
    try {
      const result = await scanDocument(file, setProgress);
      onExtracted(result.extracted_text, result.confidence);
      onClose();
    } catch (err) {
      setErrorMessage(err instanceof ScanError ? err.message : "Unable to read this document. Try a clearer, well-lit photo.");
      setState("error");
    }
  };

  const handleRetake = () => {
    setFile(null);
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
    setState("choose");
  };

  return (
    <AnimatePresence>
      {open && (
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
          <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="presentation">
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="scanner-title"
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="w-full max-w-[440px] max-h-[85vh] overflow-y-auto bg-paper rounded-[24px] p-6 md:p-8"
            >
              <div className="flex items-start justify-between mb-6">
                <div>
                  <SectionLabel>Scan document</SectionLabel>
                  <h2 id="scanner-title" className="text-lg font-medium text-carbon mt-1">
                    Scan a complaint or FIR
                  </h2>
                </div>
                <button
                  ref={closeRef}
                  onClick={onClose}
                  aria-label="Close scanner"
                  className="p-3 -mr-2 -mt-2 rounded-full hover:bg-line/60 transition-colors"
                >
                  <X className="w-5 h-5 text-carbon" strokeWidth={1.75} />
                </button>
              </div>

              {state === "choose" && (
                <div>
                  <p className="text-sm text-mercury mb-6">
                    Capture a physical document or upload a photo. Extracted text stays fully editable before analysis.
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => cameraInputRef.current?.click()}
                      className="flex flex-col items-center gap-3 rounded-[16px] border border-line bg-vellum/40 px-4 py-8 hover:bg-vellum/70 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-carbon/30"
                    >
                      <Camera className="w-6 h-6 text-carbon" strokeWidth={1.5} />
                      <span className="text-sm font-medium text-carbon">Take photo</span>
                    </button>
                    <button
                      onClick={() => galleryInputRef.current?.click()}
                      className="flex flex-col items-center gap-3 rounded-[16px] border border-line bg-vellum/40 px-4 py-8 hover:bg-vellum/70 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-carbon/30"
                    >
                      <ImagePlus className="w-6 h-6 text-carbon" strokeWidth={1.5} />
                      <span className="text-sm font-medium text-carbon">Upload photo</span>
                    </button>
                  </div>

                  <input
                    ref={cameraInputRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={(e) => handleFileSelected(e.target.files?.[0])}
                  />
                  <input
                    ref={galleryInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => handleFileSelected(e.target.files?.[0])}
                  />
                </div>
              )}

              {state === "preview" && previewUrl && (
                <div>
                  <div className="rounded-[16px] overflow-hidden border border-line mb-5 bg-vellum">
                    <img src={previewUrl} alt="Captured document preview" className="w-full max-h-[360px] object-contain" />
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <button
                      onClick={handleRetake}
                      className="inline-flex items-center gap-2 text-sm text-mercury hover:text-carbon transition-colors"
                    >
                      <RotateCcw className="w-4 h-4" strokeWidth={1.75} />
                      Retake
                    </button>
                    <button
                      onClick={handleConfirm}
                      className="px-6 py-3 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors"
                    >
                      Use this photo
                    </button>
                  </div>
                </div>
              )}

              {state === "processing" && (
                <div className="py-10 flex flex-col items-center text-center">
                  <div className="w-full h-1.5 bg-vellum rounded-full overflow-hidden mb-5" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Reading document">
                    <motion.div
                      className="h-full bg-carbon rounded-full"
                      animate={{ width: `${Math.max(6, Math.round(progress * 100))}%` }}
                      transition={{ duration: 0.2 }}
                    />
                  </div>
                  <p className="text-sm text-carbon">Reading document…</p>
                  <p className="text-xs text-mercury mt-1 tabular-nums">{Math.round(progress * 100)}%</p>
                </div>
              )}

              {state === "error" && (
                <div className="flex flex-col items-center text-center gap-4 py-8">
                  <AlertCircle className="w-6 h-6 text-[color:var(--color-priority-high)]" strokeWidth={1.5} aria-hidden="true" />
                  <div>
                    <h3 className="text-base font-medium text-carbon mb-1">Unable to read this document</h3>
                    <p className="text-sm text-mercury max-w-xs">{errorMessage}</p>
                  </div>
                  <button
                    onClick={handleRetake}
                    className="px-5 py-2.5 rounded-full text-sm font-medium bg-carbon text-vellum hover:bg-onyx transition-colors"
                  >
                    Try again
                  </button>
                </div>
              )}
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
