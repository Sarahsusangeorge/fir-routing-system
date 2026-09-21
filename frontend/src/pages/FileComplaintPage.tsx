import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import ComplaintInput from "../components/ComplaintInput";
import ComplaintScanner from "../components/ComplaintScanner";
import SectionLabel from "../components/SectionLabel";
import { useAuth } from "../context/useAuth";
import { fileCitizenComplaint } from "../services/api";
import type { CitizenComplaint } from "../types";
import { formatDate, formatDateTime, loginLabel } from "../utils/format";

const MIN_LENGTH = 15;

export default function FileComplaintPage() {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [declared, setDeclared] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filed, setFiled] = useState<CitizenComplaint | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);

  const submit = async () => {
    if (text.trim().length < MIN_LENGTH) {
      setError("Describe what happened in a little more detail before filing.");
      return;
    }
    if (!declared) {
      setError("Confirm that the information is true before filing.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      setFiled(await fileCitizenComplaint(text));
      setText("");
      setDeclared(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your complaint could not be filed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-page pt-32 pb-24">
      <SectionLabel className="mb-6">File a complaint</SectionLabel>
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-[32px] md:text-[52px] font-light leading-[1.05] tracking-[0.01em] text-carbon max-w-3xl"
      >
        {filed ? "Your complaint has been received." : "Tell the police what happened."}
      </motion.h1>

      {filed ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="bg-paper border border-line rounded-[24px] p-6 md:p-10 mt-10 md:mt-14 max-w-3xl"
        >
          <div className="flex items-start gap-4">
            <CheckCircle2
              className="w-6 h-6 mt-1 shrink-0 text-[color:var(--color-priority-low)]"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <div>
              <p className="text-sm text-mercury">Reference number</p>
              <p className="text-[34px] font-light text-carbon tabular-nums leading-tight">#{filed.complaint_id}</p>
              <p className="text-sm text-mercury mt-1">Received {formatDateTime(filed.received_at)}</p>
            </div>
          </div>

          <h2 className="text-lg font-medium text-carbon mt-10 mb-4">What happens next</h2>
          <ol className="flex flex-col gap-4 text-[15px] text-carbon/90 leading-[1.55] list-decimal pl-5">
            <li>Your complaint goes to an officer in the unit that handles this kind of case, who reviews it.</li>
            <li>
              Visit your police station to sign your complaint
              {filed.signature_due_at ? (
                <>
                  {" "}
                  by <strong className="font-medium">{formatDate(filed.signature_due_at)}</strong>
                </>
              ) : null}
              . A complaint given online must be signed within three days before it can be registered as an FIR.
              Bring your reference number and a photo ID.
            </li>
            <li>
              Follow its progress under My complaints, including the investigating officer's name and any notes they
              add for you.
            </li>
          </ol>

          <div className="flex flex-wrap items-center gap-4 mt-10">
            <Link
              to="/my-complaints"
              className="inline-flex items-center gap-2 px-7 py-3.5 rounded-full bg-carbon text-vellum text-[15px] font-medium hover:bg-onyx transition-colors"
            >
              View my complaints
              <ArrowRight className="w-4 h-4" strokeWidth={1.75} />
            </Link>
            <button
              onClick={() => setFiled(null)}
              className="text-sm text-mercury hover:text-carbon underline underline-offset-4 py-2"
            >
              File another complaint
            </button>
          </div>
        </motion.div>
      ) : (
        <>
          <p className="text-base text-mercury mt-6 max-w-xl leading-[1.55]">
            Describe the incident in your own words: what happened, when and where, and anyone involved. An officer
            will read it and decide how it is handled. In an emergency, call 112.
          </p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="bg-paper border border-line rounded-[24px] p-6 md:p-10 mt-10 md:mt-14 max-w-3xl"
          >
            <p className="text-sm text-mercury mb-6">
              Filing as <span className="text-carbon">{user?.name}</span> ({loginLabel(user)})
            </p>

            <ComplaintInput
              value={text}
              onChange={(v) => {
                setText(v);
                if (error) setError(null);
              }}
              disabled={busy}
              onScanClick={() => setScannerOpen(true)}
              label="Your complaint"
              hint="You can also photograph a written complaint and check the extracted text."
              placeholder="On the evening of..."
            />

            <label className="flex items-start gap-3 mt-6 cursor-pointer">
              <input
                type="checkbox"
                checked={declared}
                onChange={(e) => {
                  setDeclared(e.target.checked);
                  if (error) setError(null);
                }}
                className="mt-1 w-4 h-4 accent-[color:var(--color-carbon)]"
              />
              <span className="text-sm text-carbon/90 leading-[1.5]">
                The information I have given is true to the best of my knowledge. I understand that giving false
                information to the police is an offence.
              </span>
            </label>

            {error && (
              <p role="alert" className="mt-4 text-sm text-[color:var(--color-priority-high)]">
                {error}
              </p>
            )}

            <div className="flex justify-end mt-8">
              <button
                onClick={submit}
                disabled={busy}
                className="inline-flex items-center gap-2 px-7 py-3.5 rounded-full bg-carbon text-vellum text-[15px] font-medium hover:bg-onyx active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {busy ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />
                    Filing complaint...
                  </>
                ) : (
                  <>
                    File complaint
                    <ArrowRight className="w-4 h-4" strokeWidth={1.75} />
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </>
      )}

      <ComplaintScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onExtracted={(extracted) => setText(extracted)}
      />
    </div>
  );
}
