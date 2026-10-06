import { motion } from "framer-motion";
import { ArrowLeft, Loader2, Lock } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ComplaintStatusBadge from "../components/ComplaintStatusBadge";
import ErrorState from "../components/ErrorState";
import ExplainabilityViewer from "../components/ExplainabilityViewer";
import ModelBadge from "../components/ModelBadge";
import { PageLoader } from "../components/RequireRole";
import PriorityCard from "../components/PriorityCard";
import RoutingCard from "../components/RoutingCard";
import SectionCard from "../components/SectionCard";
import SectionLabel from "../components/SectionLabel";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/useAuth";
import { addDiaryEntry, fetchCase, fetchOfficers, fetchUnits, updateCase, type OfficerWorkload } from "../services/api";
import type { Complaint, ComplaintEvent, ComplaintStatus, ReviewRequest } from "../types";
import { formatDate, formatDateTime, isPast } from "../utils/format";

const fieldClass =
  "w-full rounded-[10px] border border-line bg-paper px-3.5 py-2.5 text-[15px] text-carbon focus:outline-none focus:ring-2 focus:ring-carbon/30 focus:border-carbon/40";

const EVENT_LABEL: Record<ComplaintEvent["action"], string> = {
  filed: "Filed",
  assigned: "Allocated",
  status_changed: "Status changed",
  rerouted: "Transferred",
  signature_confirmed: "Signature confirmed",
  note_added: "Note to complainant",
  diary_entry: "Case diary",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-mercury shrink-0">{label}</span>
      <span className="text-carbon text-right">{children}</span>
    </div>
  );
}

function CaseActions({ c, onUpdated }: { c: Complaint; onUpdated: (c: Complaint) => void }) {
  const { user } = useAuth();
  const ids = { status: useId(), unit: useId(), reason: useId(), note: useId(), officer: useId() };
  const review = c.review;
  const isCitizen = c.source === "citizen";
  const current = c.status ?? "New";

  const [units, setUnits] = useState<string[]>([]);
  const [officers, setOfficers] = useState<OfficerWorkload[]>([]);
  const [status, setStatus] = useState<ComplaintStatus>(current);
  const [unit, setUnit] = useState(c.routing.unit);
  const [officer, setOfficer] = useState<number | "">(c.assignment?.officer_id ?? "");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState(review?.officer_note ?? "");
  const [signed, setSigned] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    fetchUnits().then(setUnits).catch(() => setUnits([]));
    if (user?.role === "admin") fetchOfficers().then(setOfficers).catch(() => setOfficers([]));
  }, [user?.role]);

  const alreadySigned = !!review?.signature_confirmed_at;
  const unitChanged = unit !== c.routing.unit;
  const statusOptions = [current, ...(c.allowed_statuses ?? [])];

  const save = async () => {
    const request: ReviewRequest = {};
    if (status !== current) request.status = status;
    if (unitChanged) {
      request.unit = unit;
      request.override_reason = reason.trim();
    }
    if (officer !== "" && officer !== c.assignment?.officer_id) request.assigned_to = officer;
    if (signed) request.signature_confirmed = true;
    if (note.trim() !== (review?.officer_note ?? "")) request.note = note.trim();

    if (Object.keys(request).length === 0) {
      setError("Change something before saving.");
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const updated = await updateCase(c.complaint_id, request);
      setStatus(updated.status ?? "New");
      setUnit(updated.routing.unit);
      setOfficer(updated.assignment?.officer_id ?? "");
      setReason("");
      setNote(updated.review?.officer_note ?? "");
      setSigned(false);
      onUpdated(updated);
      setSaved(
        updated.assignment?.officer_id !== c.assignment?.officer_id
          ? `Saved. The case is now with ${updated.assignment?.officer_name ?? "no one"}.`
          : "Saved."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "The case could not be updated.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor={ids.status} className="block text-sm font-medium text-carbon mb-2">
            Status
          </label>
          <select
            id={ids.status}
            value={status}
            onChange={(e) => setStatus(e.target.value as ComplaintStatus)}
            className={fieldClass}
          >
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={ids.unit} className="block text-sm font-medium text-carbon mb-2">
            Unit
          </label>
          <select id={ids.unit} value={unit} onChange={(e) => setUnit(e.target.value)} className={fieldClass}>
            {(units.includes(c.routing.unit) ? units : [c.routing.unit, ...units]).map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </div>
      </div>

      {unitChanged && (
        <div>
          <label htmlFor={ids.reason} className="block text-sm font-medium text-carbon mb-2">
            Reason for transferring the case
          </label>
          <textarea
            id={ids.reason}
            rows={2}
            maxLength={1000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className={`${fieldClass} resize-none`}
            placeholder="Recorded in the audit trail. The case is re-allocated in the new unit."
          />
        </div>
      )}

      {user?.role === "admin" && officers.length > 0 && (
        <div>
          <label htmlFor={ids.officer} className="block text-sm font-medium text-carbon mb-2">
            Investigating officer
          </label>
          <select
            id={ids.officer}
            value={String(officer)}
            onChange={(e) => setOfficer(e.target.value === "" ? "" : Number(e.target.value))}
            className={fieldClass}
          >
            <option value="">Unassigned</option>
            {officers
              .filter((o) => o.active)
              .map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name} — {o.open_cases} open, {o.load_percent}% of capacity
                  {o.availability === "on_leave" ? " (on leave)" : o.availability === "busy" ? " (busy)" : ""}
                </option>
              ))}
          </select>
        </div>
      )}

      {isCitizen && !alreadySigned && (
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={signed}
            onChange={(e) => setSigned(e.target.checked)}
            className="mt-1 w-4 h-4 accent-[color:var(--color-carbon)]"
          />
          <span className="text-sm text-carbon/90 leading-[1.5]">
            The informant signed this complaint at the station. Needed before registering it, unless they have
            already signed online.
          </span>
        </label>
      )}

      <div>
        <label htmlFor={ids.note} className="block text-sm font-medium text-carbon mb-2">
          {isCitizen ? "Note to the complainant" : "Note"}
        </label>
        <textarea
          id={ids.note}
          rows={3}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className={`${fieldClass} resize-none`}
        />
        <p className="text-xs text-mercury mt-2">
          {isCitizen ? "The complainant sees this note. " : ""}Required when a case is closed or not registered.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-[color:var(--color-priority-high)]">
          {error}
        </p>
      )}
      {saved && !error && (
        <p role="status" className="text-sm text-[color:var(--color-priority-low)]">
          {saved}
        </p>
      )}

      <div className="flex justify-end">
        <button
          onClick={save}
          disabled={busy}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors disabled:opacity-40"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
          Save
        </button>
      </div>
    </div>
  );
}

function CaseDiary({ c, onUpdated }: { c: Complaint; onUpdated: (c: Complaint) => void }) {
  const [entry, setEntry] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const entries = (c.events ?? []).filter((e) => e.action === "diary_entry").reverse();

  const add = async () => {
    if (!entry.trim()) return;
    setBusy(true);
    setError(null);
    try {
      onUpdated(await addDiaryEntry(c.complaint_id, entry.trim()));
      setEntry("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The entry could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="bg-paper border border-line rounded-[24px] p-6 md:p-8">
      <SectionLabel className="mb-5">Case diary</SectionLabel>
      {c.can_act !== false && (
        <>
          <textarea
            rows={3}
            maxLength={2000}
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
            aria-label="New case diary entry"
            placeholder="What you did, who you spoke to, what you found."
            className={`${fieldClass} resize-none`}
          />
          {error && (
            <p role="alert" className="text-sm text-[color:var(--color-priority-high)] mt-3">
              {error}
            </p>
          )}
          <div className="flex justify-end mt-3">
            <button
              onClick={add}
              disabled={busy || !entry.trim()}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-line text-sm text-carbon hover:bg-vellum transition-colors disabled:opacity-40"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
              Add entry
            </button>
          </div>
        </>
      )}

      {entries.length === 0 ? (
        <p className="text-sm text-mercury mt-5">
          {c.can_act === false ? "The case diary is visible only to the officer handling this case." : "No entries yet."}
        </p>
      ) : (
        <ol className="flex flex-col gap-4 mt-6 border-l border-line pl-4">
          {entries.map((e, i) => (
            <li key={i} className="text-sm">
              <p className="text-carbon leading-[1.55]">{e.detail}</p>
              <p className="text-xs text-mercury mt-1">
                {e.actor ? `${e.actor} — ` : ""}
                {formatDateTime(e.created_at)}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export default function CasePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [c, setCase] = useState<Complaint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    fetchCase(Number(id))
      .then(setCase)
      .catch((err) => setError(err instanceof Error ? err.message : "This case could not be loaded."))
      .finally(() => setLoading(false));
  };

  useEffect(load, [id]);

  if (loading) return <PageLoader />;
  if (error || !c) {
    return (
      <div className="container-page pt-32 pb-24">
        <ErrorState title="Case not available" message={error ?? "This case could not be loaded."} onRetry={load} />
        <Link to="/cases" className="inline-flex items-center gap-2 text-sm text-mercury hover:text-carbon mt-6">
          <ArrowLeft className="w-4 h-4" strokeWidth={1.75} />
          Back to cases
        </Link>
      </div>
    );
  }

  const review = c.review;
  const readOnly = c.can_act === false;
  const signatureOverdue = !review?.signature_confirmed_at && isPast(review?.signature_due_at);

  const onUpdated = (updated: Complaint) => {
    setCase(updated);
    // An officer who transfers a case away no longer holds it.
    if (user?.role === "officer" && updated.assignment?.officer_id !== user.id) {
      navigate("/cases", {
        replace: true,
        state: {
          flash: `Case #${updated.complaint_id} is now with ${updated.assignment?.officer_name ?? "no one"} (${updated.routing.unit}).`,
        },
      });
    }
  };

  return (
    <div className="container-page pt-32 pb-24">
      <Link to="/cases" className="inline-flex items-center gap-2 text-sm text-mercury hover:text-carbon mb-6">
        <ArrowLeft className="w-4 h-4" strokeWidth={1.75} aria-hidden="true" />
        Back to cases
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="flex flex-wrap items-center gap-4"
      >
        <h1 className="text-[32px] md:text-[40px] font-light text-carbon tabular-nums">Case #{c.complaint_id}</h1>
        <ComplaintStatusBadge status={c.status ?? "New"} />
        <StatusBadge level={c.priority.level} />
      </motion.div>

      {readOnly && (
        <p className="flex items-start gap-2 text-sm text-carbon bg-paper border border-line rounded-[16px] px-5 py-4 mt-6 max-w-2xl">
          <Lock className="w-4 h-4 mt-0.5 shrink-0 text-mercury" strokeWidth={1.75} aria-hidden="true" />
          {c.restricted
            ? `This case is allocated to ${c.assignment?.officer_name ?? "no one yet"} in the ${c.routing.unit}. To protect the complainant, its account and identity are visible only to that unit, the investigating officer and administrators.`
            : `This case is allocated to ${c.assignment?.officer_name ?? "no one yet"}. You can read it, but only they or an administrator can act on it. The complainant's contact details are hidden.`}
        </p>
      )}

      <div className="grid lg:grid-cols-[1fr_380px] gap-6 lg:gap-8 mt-8 items-start">
        <div className="flex flex-col gap-6">
          <section className="bg-paper border border-line rounded-[24px] p-6 md:p-8">
            <SectionLabel className="mb-5">Complaint</SectionLabel>
            <p className="text-[15px] text-carbon/90 leading-[1.65] whitespace-pre-wrap">{c.complaint_text}</p>
          </section>

          <PriorityCard priority={c.priority} />

          <section className="bg-paper border border-line rounded-[24px] p-6 md:p-8">
            <SectionLabel className="mb-5">Detected sections</SectionLabel>
            <div className="grid sm:grid-cols-2 gap-4">
              {c.sections.map((s, i) => (
                <SectionCard key={s.code} section={s} index={i} />
              ))}
            </div>
          </section>

          <RoutingCard routing={c.routing} />

          {c.explanation.length > 0 && <ExplainabilityViewer complaintText={c.complaint_text} explanation={c.explanation} />}

          <CaseDiary c={c} onUpdated={setCase} />
        </div>

        <div className="flex flex-col gap-6 lg:sticky lg:top-28">
          <section className="bg-paper border border-line rounded-[24px] p-6">
            <SectionLabel className="mb-5">Case file</SectionLabel>
            <div className="flex flex-col gap-3">
              <Row label="Received">{formatDateTime(c.received_at)}</Row>
              {c.station && <Row label="Station">{c.station}</Row>}
              <Row label="Unit">{c.routing.unit}</Row>
              <Row label="Officer">{c.assignment?.officer_name ?? "Unassigned"}</Row>
              <Row label="Filed by">{c.source === "citizen" ? "Citizen, online" : "Officer, at the station"}</Row>
              {c.complainant && (
                <Row label="Complainant">
                  {c.complainant.name}
                  <br />
                  <span className="text-mercury">{c.complainant.phone ?? c.complainant.email}</span>
                </Row>
              )}
              {c.source === "citizen" && (
                <Row label="Signature">
                  <span className={signatureOverdue ? "text-[color:var(--color-priority-high)]" : ""}>
                    {review?.signature_confirmed_at
                      ? `${review.signature_method === "digital" ? "Signed online" : "Signed at the station"} on ${formatDate(review.signature_confirmed_at)}`
                      : review?.signature_due_at
                        ? `${signatureOverdue ? "Overdue since" : "Due by"} ${formatDate(review.signature_due_at)}`
                        : "Not confirmed"}
                  </span>
                </Row>
              )}
              {review?.original_unit && <Row label="Originally">{review.original_unit}</Row>}
              {c.model_backend && (
                <Row label="Classifier">
                  <ModelBadge backend={c.model_backend} bare />
                </Row>
              )}
            </div>
          </section>

          {!readOnly && (
            <section className="bg-paper border border-line rounded-[24px] p-6">
              <SectionLabel className="mb-5">Actions</SectionLabel>
              <CaseActions c={c} onUpdated={onUpdated} />
            </section>
          )}

          <section className="bg-paper border border-line rounded-[24px] p-6">
            <SectionLabel className="mb-5">Activity</SectionLabel>
            <ol className="flex flex-col gap-3 border-l border-line pl-4">
              {(c.events ?? [])
                .filter((e) => e.action !== "diary_entry")
                .map((e, i) => (
                  <li key={i} className="text-sm">
                    <p className="text-carbon">
                      {EVENT_LABEL[e.action] ?? e.action}
                      {e.actor && <span className="text-mercury"> — {e.actor}</span>}
                    </p>
                    {e.detail && <p className="text-mercury leading-[1.5]">{e.detail.replace(" -> ", " to ")}</p>}
                    <p className="text-xs text-mercury mt-0.5">{formatDateTime(e.created_at)}</p>
                  </li>
                ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
