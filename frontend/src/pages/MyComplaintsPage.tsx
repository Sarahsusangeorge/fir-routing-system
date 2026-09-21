import { motion } from "framer-motion";
import { ArrowRight, Loader2, PenLine } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import ComplaintStatusBadge from "../components/ComplaintStatusBadge";
import ErrorState from "../components/ErrorState";
import SectionLabel from "../components/SectionLabel";
import { useAuth } from "../context/useAuth";
import {
  confirmNumberChange,
  fetchMyComplaints,
  requestNumberChange,
  requestSignatureCode,
  signComplaint,
} from "../services/api";
import type { CitizenComplaint } from "../types";
import { formatDate, formatDateTime, formatPhone, isPast } from "../utils/format";

const fieldClass =
  "w-full rounded-[10px] border border-line bg-vellum/40 px-3.5 py-2.5 text-[15px] text-carbon focus:outline-none focus:ring-2 focus:ring-carbon/30 focus:border-carbon/40";

/**
 * Signing online, as an alternative to signing at the station. The
 * complainant re-enters a code sent to their own mobile number, which is
 * what ties the declaration to them.
 */
function SignOnline({ c, onSigned }: { c: CitizenComplaint; onSigned: (c: CitizenComplaint) => void }) {
  const codeId = useId();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [declared, setDeclared] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const channel = await requestSignatureCode(c.complaint_id);
      setSentTo(channel === "sms" ? "your mobile number" : "your email");
      setOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The code could not be sent.");
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onSigned(await signComplaint(c.complaint_id, code.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The complaint could not be signed.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <div className="mt-3">
        <button
          onClick={start}
          disabled={busy}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors disabled:opacity-40"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} /> : <PenLine className="w-4 h-4" strokeWidth={1.75} />}
          Sign online instead
        </button>
        {error && (
          <p role="alert" className="text-sm text-[color:var(--color-priority-high)] mt-2">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="mt-4 bg-vellum/60 border border-line rounded-[16px] p-5">
      <p className="text-sm text-mercury mb-4">We sent a 6-digit confirmation code to {sentTo}.</p>
      <label htmlFor={codeId} className="block text-sm font-medium text-carbon mb-2">
        Confirmation code
      </label>
      <input
        id={codeId}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        className={`${fieldClass} tracking-[0.4em] tabular-nums max-w-[220px]`}
        placeholder="000000"
      />
      <label className="flex items-start gap-3 mt-4 cursor-pointer">
        <input
          type="checkbox"
          checked={declared}
          onChange={(e) => setDeclared(e.target.checked)}
          className="mt-1 w-4 h-4 accent-[color:var(--color-carbon)]"
        />
        <span className="text-sm text-carbon/90 leading-[1.5]">
          I sign this complaint and confirm the information in it is true to the best of my knowledge.
        </span>
      </label>
      {error && (
        <p role="alert" className="text-sm text-[color:var(--color-priority-high)] mt-3">
          {error}
        </p>
      )}
      <div className="flex items-center gap-4 mt-4">
        <button
          onClick={submit}
          disabled={busy || code.length !== 6 || !declared}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors disabled:opacity-40"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
          Sign complaint
        </button>
        <button onClick={() => setOpen(false)} className="text-sm text-mercury hover:text-carbon py-2">
          Cancel
        </button>
      </div>
    </div>
  );
}

/** Moving the account to a new mobile number, keeping every complaint. */
function ChangeNumber() {
  const { user } = useAuth();
  const ids = { phone: useId(), code: useId() };
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  if (!user?.phone) return null;

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      setSentTo(await requestNumberChange(phone.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The code could not be sent.");
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await confirmNumberChange(sentTo!, code.trim());
      setDone(`Your number is now ${formatPhone(res.user.phone)}. Your complaints stay on this account.`);
      setOpen(false);
      setSentTo(null);
      setPhone("");
      setCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The number could not be changed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-6">
      {done && (
        <p role="status" className="text-sm text-[color:var(--color-priority-low)] mb-2">
          {done}
        </p>
      )}
      {!open ? (
        <p className="text-sm text-mercury">
          Signed in as {formatPhone(user.phone)}.{" "}
          <button onClick={() => setOpen(true)} className="underline underline-offset-4 hover:text-carbon">
            Change your mobile number
          </button>
        </p>
      ) : (
        <div className="bg-paper border border-line rounded-[16px] p-5 max-w-lg">
          <p className="text-sm text-mercury mb-4">
            Your complaints stay with this account. The old number will no longer open it.
          </p>
          {!sentTo ? (
            <>
              <label htmlFor={ids.phone} className="block text-sm font-medium text-carbon mb-2">
                New mobile number
              </label>
              <input
                id={ids.phone}
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className={fieldClass}
                placeholder="98765 43210"
              />
            </>
          ) : (
            <>
              <label htmlFor={ids.code} className="block text-sm font-medium text-carbon mb-2">
                Code sent to {formatPhone(sentTo)}
              </label>
              <input
                id={ids.code}
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className={`${fieldClass} tracking-[0.4em] tabular-nums max-w-[220px]`}
                placeholder="000000"
              />
            </>
          )}
          {error && (
            <p role="alert" className="text-sm text-[color:var(--color-priority-high)] mt-3">
              {error}
            </p>
          )}
          <div className="flex items-center gap-4 mt-4">
            <button
              onClick={sentTo ? confirm : send}
              disabled={busy || (sentTo ? code.length !== 6 : !phone.trim())}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors disabled:opacity-40"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
              {sentTo ? "Confirm new number" : "Send code"}
            </button>
            <button
              onClick={() => {
                setOpen(false);
                setSentTo(null);
                setError(null);
              }}
              className="text-sm text-mercury hover:text-carbon py-2"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function SignatureLine({ c }: { c: CitizenComplaint }) {
  if (c.signature_confirmed_at) {
    return (
      <p className="text-sm text-mercury">
        {c.signature_method === "digital" ? "Signed online" : "Signed at the station"} on{" "}
        {formatDate(c.signature_confirmed_at)}.
      </p>
    );
  }
  if (c.status !== "New" && c.status !== "Under Review") return null;
  if (!c.signature_due_at) return null;
  const overdue = isPast(c.signature_due_at);
  return (
    <p className={`text-sm ${overdue ? "text-[color:var(--color-priority-high)]" : "text-carbon"}`}>
      {overdue
        ? `The signing window closed on ${formatDate(c.signature_due_at)}. Contact your police station about this complaint.`
        : `Sign this complaint by ${formatDate(c.signature_due_at)} — online below, or at your police station.`}
    </p>
  );
}

function ComplaintItem({ c, onUpdated }: { c: CitizenComplaint; onUpdated: (c: CitizenComplaint) => void }) {
  const [expanded, setExpanded] = useState(false);
  const long = c.complaint_text.length > 220;
  return (
    <li className="py-6 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span className="text-lg text-carbon tabular-nums">#{c.complaint_id}</span>
          <span className="text-sm text-mercury">{formatDateTime(c.received_at)}</span>
        </div>
        <ComplaintStatusBadge status={c.status} />
      </div>

      <p className="text-[15px] text-carbon/90 leading-[1.6] mt-3 max-w-[70ch]">
        {long && !expanded ? `${c.complaint_text.slice(0, 220).trim()}…` : c.complaint_text}
      </p>
      {long && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-sm text-mercury hover:text-carbon underline underline-offset-4 mt-1 py-1"
        >
          {expanded ? "Show less" : "Show full complaint"}
        </button>
      )}

      <dl className="grid sm:grid-cols-[160px_1fr] gap-x-6 gap-y-1 sm:gap-y-2 mt-5 text-sm">
        <dt className="text-mercury">Handled by</dt>
        <dd className="text-carbon mb-2 sm:mb-0">
          {c.unit ? (c.officer ? `${c.officer}, ${c.unit}` : c.unit) : "Awaiting officer review"}
          {c.officer_station && <span className="block text-mercury">{c.officer_station}</span>}
        </dd>
        {c.officer_note && (
          <>
            <dt className="text-mercury">Note from the police</dt>
            <dd className="text-carbon leading-[1.5]">{c.officer_note}</dd>
          </>
        )}
      </dl>
      <div className="mt-4">
        <SignatureLine c={c} />
        {c.can_sign_digitally && <SignOnline c={c} onSigned={onUpdated} />}
      </div>
    </li>
  );
}

export default function MyComplaintsPage() {
  const [complaints, setComplaints] = useState<CitizenComplaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    fetchMyComplaints()
      .then(setComplaints)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div className="container-page pt-32 pb-24">
      <SectionLabel className="mb-6">My complaints</SectionLabel>
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-[32px] font-normal text-carbon max-w-2xl"
      >
        Your complaints and their progress
      </motion.h1>
      <p className="text-base text-mercury mt-4 max-w-xl">
        A complaint is registered as an FIR once an officer has reviewed it and you have signed it, online or at the
        station. After that, you can follow the investigation here.
      </p>

      <ChangeNumber />

      <div className="bg-paper border border-line rounded-[24px] p-6 md:p-8 mt-10 max-w-4xl">
        {error ? (
          <ErrorState
            title="Your complaints could not be loaded"
            message="Check your connection and try again."
            onRetry={load}
          />
        ) : loading ? (
          <div className="flex flex-col gap-6 animate-pulse" aria-label="Loading">
            {[0, 1].map((i) => (
              <div key={i} className="flex flex-col gap-3">
                <div className="h-5 w-40 bg-line rounded" />
                <div className="h-4 w-full bg-line rounded" />
                <div className="h-4 w-2/3 bg-line rounded" />
              </div>
            ))}
          </div>
        ) : complaints.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-carbon">You haven't filed a complaint yet.</p>
            <Link
              to="/file"
              className="inline-flex items-center gap-2 mt-5 px-6 py-3 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors"
            >
              File a complaint
              <ArrowRight className="w-4 h-4" strokeWidth={1.75} />
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {complaints.map((c) => (
              <ComplaintItem
                key={c.complaint_id}
                c={c}
                onUpdated={(updated) =>
                  setComplaints((list) => list.map((x) => (x.complaint_id === updated.complaint_id ? updated : x)))
                }
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
