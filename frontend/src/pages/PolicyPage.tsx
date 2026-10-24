import { motion } from "framer-motion";
import { Loader2, Trash2 } from "lucide-react";
import { useEffect, useId, useMemo, useState } from "react";
import ErrorState from "../components/ErrorState";
import SectionLabel from "../components/SectionLabel";
import {
  createRoutingRule,
  deleteRoutingRule,
  fetchPolicyChanges,
  fetchRoutingPolicy,
  fetchSections,
  toIsoUtc,
  updateRoutingRule,
  updateSection,
} from "../services/api";
import type { IpcSection, PolicyChange, RoutingPolicy, RoutingRule } from "../types";
import { formatDateTime } from "../utils/format";

const fieldClass =
  "w-full rounded-[10px] border border-line bg-vellum/40 px-3 py-2 text-[15px] text-carbon focus:outline-none focus:ring-2 focus:ring-carbon/30 focus:border-carbon/40";

const numberClass = `${fieldClass} w-24 tabular-nums`;

/**
 * Severity weights, with the rubric the seed data follows. Changing one
 * changes the priority of every complaint analysed afterwards, which is why
 * the rubric is restated here rather than left in the paper.
 */
function SeverityTable({
  sections,
  onChanged,
}: {
  sections: IpcSection[];
  onChanged: (s: IpcSection, message: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const filterId = useId();

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return sections;
    return sections.filter(
      (s) => s.code.toLowerCase().includes(needle) || s.title.toLowerCase().includes(needle)
    );
  }, [sections, filter]);

  const save = async (section: IpcSection) => {
    const raw = drafts[section.code];
    if (raw === undefined) return;
    const weight = Number(raw);
    if (!raw || Number.isNaN(weight) || weight < 1 || weight > 10) {
      setError(`Severity for Section ${section.code} must be a number between 1 and 10.`);
      return;
    }
    setPending(section.code);
    setError(null);
    try {
      const updated = await updateSection(section.code, { severity_weight: weight });
      setDrafts((d) => {
        const next = { ...d };
        delete next[section.code];
        return next;
      });
      onChanged(
        updated,
        `Section ${section.code} now carries severity ${weight}. Complaints analysed from now on use it; ` +
          `results already recorded are unchanged.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "The severity weight could not be saved.");
    } finally {
      setPending(null);
    }
  };

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        <div>
          <label htmlFor={filterId} className="block text-sm font-medium text-carbon mb-2">
            Find a section
          </label>
          <input
            id={filterId}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="302, theft, hurt…"
            className={`${fieldClass} sm:w-72`}
          />
        </div>
        <p className="text-xs text-mercury max-w-sm">
          Rubric: 9–10 death or life; 7–8 cognizable and non-bailable, 7 years or more; 4–6 cognizable, up to 7
          years; 1–3 non-cognizable or bailable, or a definitional provision.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-[color:var(--color-priority-high)] mb-4">
          {error}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[680px]">
          <thead>
            <tr className="border-b border-line text-sm text-mercury">
              <th className="py-3 pr-4 font-normal">Section</th>
              <th className="py-3 pr-4 font-normal">Classification</th>
              <th className="py-3 pr-4 font-normal">Maximum punishment</th>
              <th className="py-3 pr-4 font-normal">Severity</th>
              <th className="py-3 font-normal text-right">&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((s) => {
              const draft = drafts[s.code];
              const dirty = draft !== undefined && Number(draft) !== s.severity_weight;
              return (
                <tr key={s.code} className="border-b border-line last:border-0">
                  <td className="py-3 pr-4">
                    <p className="text-sm text-carbon">Section {s.code}</p>
                    <p className="text-xs text-mercury">{s.title}</p>
                  </td>
                  <td className="py-3 pr-4 text-sm text-carbon">
                    {s.cognizable ? "Cognizable" : "Non-cognizable"}
                    <span className="block text-xs text-mercury">{s.bailable ? "Bailable" : "Non-bailable"}</span>
                  </td>
                  <td className="py-3 pr-4 text-sm text-carbon whitespace-nowrap">
                    {s.max_punishment_years === null
                      ? "Life or death"
                      : `${s.max_punishment_years} year${s.max_punishment_years === 1 ? "" : "s"}`}
                  </td>
                  <td className="py-3 pr-4">
                    <label className="sr-only" htmlFor={`sev-${s.code}`}>
                      Severity weight for Section {s.code}
                    </label>
                    <input
                      id={`sev-${s.code}`}
                      type="number"
                      min={1}
                      max={10}
                      step={0.5}
                      inputMode="decimal"
                      value={draft ?? String(s.severity_weight)}
                      onChange={(e) => setDrafts((d) => ({ ...d, [s.code]: e.target.value }))}
                      className={numberClass}
                    />
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => save(s)}
                      disabled={!dirty || pending === s.code}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-line text-sm text-carbon hover:bg-vellum transition-colors disabled:opacity-30"
                    >
                      {pending === s.code && <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.75} />}
                      Save
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {visible.length === 0 && <p className="text-sm text-mercury py-6">No section matches that search.</p>}
      </div>
    </>
  );
}

/** Which unit handles which section, and in what order of precedence. */
function RoutingTable({
  policy,
  sections,
  onReload,
  onNotice,
}: {
  policy: RoutingPolicy;
  sections: IpcSection[];
  onReload: () => void;
  onNotice: (message: string) => void;
}) {
  const ids = { section: useId(), unit: useId(), precedence: useId() };
  const [draft, setDraft] = useState({ section_code: "", unit: "", precedence: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const precedence = Number(draft.precedence);
    if (!draft.section_code || !draft.unit.trim() || !Number.isInteger(precedence) || precedence < 1) {
      setError("Choose a section, name the unit and give a whole-number precedence of 1 or more.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await createRoutingRule({
        section_code: draft.section_code,
        unit: draft.unit.trim(),
        precedence,
      });
      setDraft({ section_code: "", unit: "", precedence: "" });
      onNotice(
        result.officers_available === 0
          ? `Rule added, but no active officer serves ${result.rule.unit}, so cases routed there will wait unassigned.`
          : `Rule added. ${result.officers_available} officer${result.officers_available === 1 ? "" : "s"} serve ${result.rule.unit}.`
      );
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The rule could not be added.");
    } finally {
      setBusy(false);
    }
  };

  const change = async (rule: RoutingRule, changes: { unit?: string; precedence?: number }) => {
    setPendingId(rule.id);
    setError(null);
    try {
      const result = await updateRoutingRule(rule.id, changes);
      onNotice(
        result.officers_available === 0
          ? `Section ${rule.section_code} now routes to ${result.rule.unit}, which no active officer serves.`
          : `Section ${rule.section_code} now routes to ${result.rule.unit}.`
      );
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The rule could not be changed.");
    } finally {
      setPendingId(null);
    }
  };

  const remove = async (rule: RoutingRule) => {
    if (
      !window.confirm(
        `Remove the rule sending Section ${rule.section_code} to ${rule.unit}? ` +
          `Complaints citing it will fall back to ${policy.default_unit} unless another rule matches.`
      )
    ) {
      return;
    }
    setPendingId(rule.id);
    setError(null);
    try {
      await deleteRoutingRule(rule.id);
      onNotice(`Rule removed. Section ${rule.section_code} no longer routes to ${rule.unit}.`);
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The rule could not be removed.");
    } finally {
      setPendingId(null);
    }
  };

  return (
    <>
      <p className="text-sm text-mercury mb-6 max-w-2xl">
        Lower precedence wins when a complaint matches several sections, which is what makes routing victim-centric:
        offences against women and children outrank general violent crime. A complaint matching no rule goes to{" "}
        {policy.default_unit}.
      </p>

      {error && (
        <p role="alert" className="text-sm text-[color:var(--color-priority-high)] mb-4">
          {error}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[720px]">
          <thead>
            <tr className="border-b border-line text-sm text-mercury">
              <th className="py-3 pr-4 font-normal">Section</th>
              <th className="py-3 pr-4 font-normal">Unit</th>
              <th className="py-3 pr-4 font-normal">Precedence</th>
              <th className="py-3 pr-4 font-normal">Officers</th>
              <th className="py-3 font-normal text-right">&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {policy.rules.map((rule) => {
              const staffed = policy.officers_by_unit[rule.unit] ?? 0;
              return (
                <tr key={rule.id} className="border-b border-line last:border-0">
                  <td className="py-3 pr-4">
                    <p className="text-sm text-carbon">Section {rule.section_code}</p>
                    {rule.section_title && <p className="text-xs text-mercury">{rule.section_title}</p>}
                  </td>
                  <td className="py-3 pr-4">
                    <label className="sr-only" htmlFor={`unit-${rule.id}`}>
                      Unit for Section {rule.section_code}
                    </label>
                    <select
                      id={`unit-${rule.id}`}
                      value={rule.unit}
                      disabled={pendingId === rule.id}
                      onChange={(e) => change(rule, { unit: e.target.value })}
                      className={`${fieldClass} sm:w-60`}
                    >
                      {[...new Set([...policy.units, rule.unit])].sort().map((u) => (
                        <option key={u} value={u}>
                          {u}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-3 pr-4">
                    <label className="sr-only" htmlFor={`prec-${rule.id}`}>
                      Precedence for Section {rule.section_code}
                    </label>
                    <input
                      id={`prec-${rule.id}`}
                      type="number"
                      min={1}
                      max={999}
                      inputMode="numeric"
                      defaultValue={rule.precedence}
                      disabled={pendingId === rule.id}
                      onBlur={(e) => {
                        const value = Number(e.target.value);
                        if (Number.isInteger(value) && value !== rule.precedence && value >= 1 && value <= 999) {
                          change(rule, { precedence: value });
                        }
                      }}
                      className={numberClass}
                    />
                  </td>
                  <td className="py-3 pr-4 text-sm tabular-nums">
                    {staffed === 0 ? (
                      <span className="text-[color:var(--color-priority-high)]">None</span>
                    ) : (
                      <span className="text-carbon">{staffed}</span>
                    )}
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => remove(rule)}
                      disabled={pendingId === rule.id}
                      aria-label={`Remove the rule sending Section ${rule.section_code} to ${rule.unit}`}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-full border border-line text-sm text-carbon hover:bg-vellum transition-colors disabled:opacity-30"
                    >
                      {pendingId === rule.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.75} />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" strokeWidth={1.75} aria-hidden="true" />
                      )}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <form onSubmit={add} className="grid sm:grid-cols-4 gap-4 items-end mt-8 pt-6 border-t border-line" noValidate>
        <div>
          <label htmlFor={ids.section} className="block text-sm font-medium text-carbon mb-2">
            Section
          </label>
          <select
            id={ids.section}
            value={draft.section_code}
            onChange={(e) => setDraft((d) => ({ ...d, section_code: e.target.value }))}
            className={fieldClass}
          >
            <option value="">Choose…</option>
            {sections.map((s) => (
              <option key={s.code} value={s.code}>
                {s.code} — {s.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={ids.unit} className="block text-sm font-medium text-carbon mb-2">
            Unit
          </label>
          <input
            id={ids.unit}
            list="policy-units"
            value={draft.unit}
            onChange={(e) => setDraft((d) => ({ ...d, unit: e.target.value }))}
            className={fieldClass}
          />
          <datalist id="policy-units">
            {policy.units.map((u) => (
              <option key={u} value={u} />
            ))}
          </datalist>
        </div>
        <div>
          <label htmlFor={ids.precedence} className="block text-sm font-medium text-carbon mb-2">
            Precedence
          </label>
          <input
            id={ids.precedence}
            type="number"
            min={1}
            max={999}
            inputMode="numeric"
            value={draft.precedence}
            onChange={(e) => setDraft((d) => ({ ...d, precedence: e.target.value }))}
            className={fieldClass}
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors disabled:opacity-40"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
          Add rule
        </button>
      </form>
    </>
  );
}

function ChangeLog({ changes }: { changes: PolicyChange[] }) {
  if (changes.length === 0) {
    return <p className="text-sm text-mercury">No policy change has been recorded yet.</p>;
  }
  return (
    <ul className="space-y-3">
      {changes.slice(0, 25).map((c) => (
        <li key={c.id} className="text-sm text-carbon border-b border-line pb-3 last:border-0">
          <span className="text-mercury">{formatDateTime(toIsoUtc(c.changed_at))} · </span>
          {c.actor_name ?? "An administrator"}{" "}
          {c.field === "created"
            ? `added routing rule ${c.new_value}`
            : c.field === "deleted"
              ? `removed routing rule ${c.old_value}`
              : `changed ${c.field.replace(/_/g, " ")} on ${
                  c.entity === "ipc_section" ? `Section ${c.record_key}` : `routing rule ${c.record_key}`
                } from ${c.old_value} to ${c.new_value}`}
        </li>
      ))}
    </ul>
  );
}

export default function PolicyPage() {
  const [sections, setSections] = useState<IpcSection[]>([]);
  const [policy, setPolicy] = useState<RoutingPolicy | null>(null);
  const [changes, setChanges] = useState<PolicyChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<"severity" | "routing">("severity");

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([fetchSections(), fetchRoutingPolicy(), fetchPolicyChanges()])
      .then(([s, p, c]) => {
        setSections(s);
        setPolicy(p);
        setChanges(c);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const refresh = () => {
    Promise.all([fetchSections(), fetchRoutingPolicy(), fetchPolicyChanges()])
      .then(([s, p, c]) => {
        setSections(s);
        setPolicy(p);
        setChanges(c);
      })
      .catch(() => setError(true));
  };

  return (
    <div className="container-page pt-32 pb-24">
      <SectionLabel className="mb-6">Decision policy</SectionLabel>
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-[32px] font-normal text-carbon max-w-2xl"
      >
        Severity weights and routing rules
      </motion.h1>
      <p className="text-base text-mercury mt-4 max-w-xl">
        Priority and routing are decided by these two tables rather than by the model, so policy can change here
        without retraining anything. A change applies to complaints analysed from that point on; results already
        recorded against a case are never rewritten. Every change is kept below with the administrator who made it.
      </p>

      {notice && (
        <p role="status" className="mt-6 max-w-2xl text-sm text-carbon bg-paper border border-line rounded-[16px] px-5 py-4">
          {notice}
        </p>
      )}

      {error ? (
        <div className="mt-10">
          <ErrorState title="Decision policy could not be loaded" message="Try again in a moment." onRetry={load} />
        </div>
      ) : loading || !policy ? (
        <div className="flex justify-center py-16">
          <Loader2 className="w-5 h-5 animate-spin text-mercury" strokeWidth={1.75} />
        </div>
      ) : (
        <>
          <div role="tablist" aria-label="Decision policy" className="flex gap-2 mt-10">
            {(
              [
                ["severity", "Severity weights"],
                ["routing", "Routing rules"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                role="tab"
                id={`tab-${value}`}
                aria-selected={tab === value}
                aria-controls={`panel-${value}`}
                onClick={() => setTab(value)}
                className={`px-5 py-2.5 rounded-full text-sm border transition-colors ${
                  tab === value ? "bg-carbon text-vellum border-carbon" : "border-line text-carbon hover:bg-vellum"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
            className="bg-paper border border-line rounded-[24px] p-6 md:p-8 mt-6"
          >
            {tab === "severity" ? (
              <SeverityTable
                sections={sections}
                onChanged={(updated, message) => {
                  setSections((list) => list.map((s) => (s.code === updated.code ? updated : s)));
                  setNotice(message);
                  refresh();
                }}
              />
            ) : (
              <RoutingTable
                policy={policy}
                sections={sections}
                onReload={refresh}
                onNotice={(message) => setNotice(message)}
              />
            )}
          </div>

          <div className="bg-paper border border-line rounded-[24px] p-6 md:p-8 mt-6">
            <h2 className="text-lg font-medium text-carbon mb-6">Recent policy changes</h2>
            <ChangeLog changes={changes} />
          </div>
        </>
      )}
    </div>
  );
}
