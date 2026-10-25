import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { Fragment, useEffect, useId, useState } from "react";
import ErrorState from "../components/ErrorState";
import SectionLabel from "../components/SectionLabel";
import { useAuth } from "../context/useAuth";
import { createStaff, fetchStaff, fetchStations, fetchUnits, toIsoUtc, updateStaff } from "../services/api";
import type { NewStaffAccount, StaffAccount, Station } from "../types";
import { formatDateTime } from "../utils/format";

const fieldClass =
  "w-full rounded-[10px] border border-line bg-vellum/40 px-3.5 py-2.5 text-[15px] text-carbon focus:outline-none focus:ring-2 focus:ring-carbon/30 focus:border-carbon/40";

const EMPTY: NewStaffAccount = {
  name: "",
  email: "",
  role: "officer",
  password: "",
  unit: "",
  username: "",
  station: "",
  capacity: null,
};

/** Mirrors the server's rule, so the field can be corrected before submitting. */
const USERNAME_RE = /^[a-z0-9._-]{3,32}$/;

const AVAILABILITY_LABEL: Record<string, string> = {
  available: "Available",
  busy: "Busy",
  on_leave: "On leave",
};

function CreateStaffForm({
  units,
  stations,
  onCreated,
}: {
  units: string[];
  stations: Station[];
  onCreated: (a: StaffAccount) => void;
}) {
  const ids = {
    name: useId(),
    email: useId(),
    username: useId(),
    role: useId(),
    unit: useId(),
    station: useId(),
    capacity: useId(),
    password: useId(),
  };
  const [form, setForm] = useState<NewStaffAccount>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<string | null>(null);

  const set = <K extends keyof NewStaffAccount>(key: K, value: NewStaffAccount[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setError(null);
    setCreated(null);
  };

  const isOfficer = form.role === "officer";
  const username = (form.username ?? "").trim().toLowerCase();
  const usernameProblem = username && !USERNAME_RE.test(username)
    ? "Use 3-32 characters: lower-case letters, digits, dot, dash or underscore."
    : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (usernameProblem) {
      setError(usernameProblem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await createStaff({
        ...form,
        name: form.name.trim(),
        email: form.email.trim(),
        username: username || null,
        unit: isOfficer && form.unit ? form.unit : null,
        station: isOfficer && form.station ? form.station : null,
        capacity: isOfficer && form.capacity ? form.capacity : null,
      });
      onCreated(result.user);
      const picked = result.cases_assigned
        ? ` ${result.cases_assigned} waiting case${result.cases_assigned === 1 ? "" : "s"} allocated to them.`
        : "";
      setCreated(
        `${result.user.name} can now sign in as ${result.user.username ?? result.user.email}. ` +
          `Share the temporary password privately.${picked}`
      );
      setForm(EMPTY);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The account could not be created.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="grid sm:grid-cols-2 gap-5" noValidate>
      <div>
        <label htmlFor={ids.name} className="block text-sm font-medium text-carbon mb-2">
          Full name
        </label>
        <input id={ids.name} value={form.name} onChange={(e) => set("name", e.target.value)} className={fieldClass} />
      </div>
      <div>
        <label htmlFor={ids.email} className="block text-sm font-medium text-carbon mb-2">
          Official email
        </label>
        <input
          id={ids.email}
          type="email"
          autoComplete="off"
          value={form.email}
          onChange={(e) => set("email", e.target.value)}
          className={fieldClass}
        />
      </div>
      <div>
        <label htmlFor={ids.username} className="block text-sm font-medium text-carbon mb-2">
          Username <span className="text-mercury font-normal">(optional)</span>
        </label>
        <input
          id={ids.username}
          autoComplete="off"
          value={form.username ?? ""}
          onChange={(e) => set("username", e.target.value)}
          aria-describedby={`${ids.username}-hint`}
          aria-invalid={usernameProblem ? true : undefined}
          className={fieldClass}
        />
        <p id={`${ids.username}-hint`} className="text-xs text-mercury mt-2">
          {usernameProblem ?? "What they type to sign in. Their email is used if this is left blank."}
        </p>
      </div>
      <div>
        <label htmlFor={ids.role} className="block text-sm font-medium text-carbon mb-2">
          Role
        </label>
        <select
          id={ids.role}
          value={form.role}
          onChange={(e) => set("role", e.target.value as NewStaffAccount["role"])}
          className={fieldClass}
        >
          <option value="officer">Officer</option>
          <option value="admin">Administrator</option>
        </select>
      </div>
      <div>
        <label htmlFor={ids.unit} className="block text-sm font-medium text-carbon mb-2">
          Unit
        </label>
        <select
          id={ids.unit}
          value={isOfficer ? form.unit ?? "" : ""}
          disabled={!isOfficer}
          onChange={(e) => set("unit", e.target.value)}
          className={`${fieldClass} disabled:opacity-50`}
        >
          <option value="">All units (duty officer)</option>
          {units.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={ids.station} className="block text-sm font-medium text-carbon mb-2">
          Station
        </label>
        <select
          id={ids.station}
          value={isOfficer ? form.station ?? "" : ""}
          disabled={!isOfficer}
          onChange={(e) => set("station", e.target.value)}
          aria-describedby={`${ids.station}-hint`}
          className={`${fieldClass} disabled:opacity-50`}
        >
          <option value="">No station set</option>
          {stations.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name}
            </option>
          ))}
        </select>
        <p id={`${ids.station}-hint`} className="text-xs text-mercury mt-2">
          Cases are kept at the station where they were filed, so an officer without one is only ever a fallback.
        </p>
      </div>
      <div>
        <label htmlFor={ids.capacity} className="block text-sm font-medium text-carbon mb-2">
          Caseload capacity
        </label>
        <input
          id={ids.capacity}
          type="number"
          min={1}
          max={100}
          inputMode="numeric"
          disabled={!isOfficer}
          value={form.capacity ?? ""}
          onChange={(e) => set("capacity", e.target.value ? Number(e.target.value) : null)}
          aria-describedby={`${ids.capacity}-hint`}
          className={`${fieldClass} disabled:opacity-50`}
        />
        <p id={`${ids.capacity}-hint`} className="text-xs text-mercury mt-2">
          Weighted cases before they count as over capacity. Leave blank for the default of 10.
        </p>
      </div>
      <div className="sm:col-span-2">
        <label htmlFor={ids.password} className="block text-sm font-medium text-carbon mb-2">
          Temporary password
        </label>
        <input
          id={ids.password}
          type="password"
          autoComplete="new-password"
          value={form.password}
          onChange={(e) => set("password", e.target.value)}
          className={fieldClass}
        />
        <p className="text-xs text-mercury mt-2">At least 10 characters, with upper- and lower-case letters and a number.</p>
      </div>

      <div className="sm:col-span-2 flex flex-wrap items-center justify-between gap-4">
        <div className="text-sm">
          {error && (
            <p role="alert" className="text-[color:var(--color-priority-high)]">
              {error}
            </p>
          )}
          {created && (
            <p role="status" className="text-[color:var(--color-priority-low)]">
              {created}
            </p>
          )}
        </div>
        <button
          type="submit"
          disabled={busy || !form.name.trim() || !form.email.trim() || !form.password}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors disabled:opacity-40"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
          Create account
        </button>
      </div>
    </form>
  );
}

/**
 * Per-officer posting and capacity, and a password reset for any staff
 * account. Capacity and station feed the allocation rule directly, so an
 * administrator has to be able to correct them without a database client.
 */
function EditStaffPanel({
  account,
  stations,
  onSaved,
  onClose,
}: {
  account: StaffAccount;
  stations: Station[];
  onSaved: (a: StaffAccount, notice: string | null) => void;
  onClose: () => void;
}) {
  const ids = { station: useId(), capacity: useId(), password: useId() };
  const [station, setStation] = useState(account.station ?? "");
  const [capacity, setCapacity] = useState<string>(account.capacity ? String(account.capacity) : "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOfficer = account.role === "officer";

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const changes: Parameters<typeof updateStaff>[1] = {};
      if (isOfficer && station !== (account.station ?? "")) changes.station = station || null;
      if (isOfficer && capacity !== (account.capacity ? String(account.capacity) : "")) {
        const value = Number(capacity);
        if (!capacity || !Number.isInteger(value) || value < 1 || value > 100) {
          setError("Capacity must be a whole number between 1 and 100.");
          setBusy(false);
          return;
        }
        changes.capacity = value;
      }
      if (password) changes.password = password;

      if (Object.keys(changes).length === 0) {
        onClose();
        return;
      }

      const result = await updateStaff(account.id, changes);
      const notices: string[] = [];
      if (password) notices.push(`${account.name} was signed out everywhere and must use the new password.`);
      if (result.cases_moved) {
        notices.push(`${result.cases_moved} open case${result.cases_moved === 1 ? "" : "s"} moved to other officers.`);
      }
      if (result.cases_assigned) {
        notices.push(
          `${result.cases_assigned} waiting case${result.cases_assigned === 1 ? "" : "s"} allocated to them.`
        );
      }
      onSaved(result.user, notices.join(" ") || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The account could not be updated.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="border-b border-line bg-vellum/30">
      <td colSpan={6} className="px-4 py-5">
        <div className="grid sm:grid-cols-3 gap-5">
          {isOfficer && (
            <>
              <div>
                <label htmlFor={ids.station} className="block text-sm font-medium text-carbon mb-2">
                  Station
                </label>
                <select
                  id={ids.station}
                  value={station}
                  onChange={(e) => setStation(e.target.value)}
                  className={fieldClass}
                >
                  <option value="">No station set</option>
                  {stations.map((s) => (
                    <option key={s.code} value={s.code}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={ids.capacity} className="block text-sm font-medium text-carbon mb-2">
                  Caseload capacity
                </label>
                <input
                  id={ids.capacity}
                  type="number"
                  min={1}
                  max={100}
                  inputMode="numeric"
                  value={capacity}
                  onChange={(e) => setCapacity(e.target.value)}
                  placeholder="10"
                  className={fieldClass}
                />
              </div>
            </>
          )}
          <div className={isOfficer ? "" : "sm:col-span-2"}>
            <label htmlFor={ids.password} className="block text-sm font-medium text-carbon mb-2">
              Reset password
            </label>
            <input
              id={ids.password}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Leave blank to keep the current one"
              aria-describedby={`${ids.password}-hint`}
              className={fieldClass}
            />
            <p id={`${ids.password}-hint`} className="text-xs text-mercury mt-2">
              Resetting ends every session they have open.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 mt-5">
          <p role="alert" className="text-sm text-[color:var(--color-priority-high)]">
            {error}
          </p>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-full border border-line text-sm text-carbon hover:bg-vellum transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={save}
              disabled={busy}
              className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-carbon text-vellum text-sm font-medium hover:bg-onyx transition-colors disabled:opacity-40"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
              Save changes
            </button>
          </div>
        </div>
      </td>
    </tr>
  );
}

export default function StaffPage() {
  const { user } = useAuth();
  const [staff, setStaff] = useState<StaffAccount[]>([]);
  const [units, setUnits] = useState<string[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const [rowNotice, setRowNotice] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([fetchStaff(), fetchUnits(), fetchStations()])
      .then(([s, u, st]) => {
        setStaff(s);
        setUnits(u);
        setStations(st);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const stationName = (code?: string | null) =>
    code ? (stations.find((s) => s.code === code)?.name ?? code) : null;

  const toggleActive = async (account: StaffAccount) => {
    if (account.active) {
      const consequence =
        account.role === "officer" && account.open_cases > 0
          ? ` Their ${account.open_cases} open case${account.open_cases === 1 ? "" : "s"} will be moved to other officers, and they will be signed out everywhere.`
          : " They will be signed out everywhere.";
      if (!window.confirm(`Deactivate ${account.name}?${consequence}`)) return;
    }
    setPendingId(account.id);
    setRowError(null);
    try {
      const result = await updateStaff(account.id, { active: !account.active });
      setStaff((list) => list.map((s) => (s.id === result.user.id ? result.user : s)));
      setRowNotice(
        result.cases_moved
          ? `${result.cases_moved} open case${result.cases_moved === 1 ? "" : "s"} moved to other officers.`
          : result.cases_assigned
            ? `${result.cases_assigned} waiting case${result.cases_assigned === 1 ? "" : "s"} allocated to them.`
            : null
      );
    } catch (err) {
      setRowError(err instanceof Error ? err.message : "The account could not be updated.");
    } finally {
      setPendingId(null);
    }
  };

  return (
    <div className="container-page pt-32 pb-24">
      <SectionLabel className="mb-6">Staff</SectionLabel>
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-[32px] font-normal text-carbon max-w-2xl"
      >
        Staff accounts
      </motion.h1>
      <p className="text-base text-mercury mt-4 max-w-xl">
        Officers and administrators can only be added here. New cases are allocated to officers by unit, station and
        workload. Every officer can see the district's case list and who holds each case, but only the assigned
        officer or an administrator can act on a case, and sexual-offence and Women &amp; Child Protection Unit cases
        are readable only by that unit.
      </p>

      <div className="bg-paper border border-line rounded-[24px] p-6 md:p-8 mt-10">
        <h2 className="text-lg font-medium text-carbon mb-6">Add a staff member</h2>
        <CreateStaffForm units={units} stations={stations} onCreated={(a) => setStaff((list) => [...list, a])} />
      </div>

      <div className="bg-paper border border-line rounded-[24px] p-6 md:p-8 mt-6">
        <h2 className="text-lg font-medium text-carbon mb-6">Current staff</h2>
        {rowError && (
          <p role="alert" className="text-sm text-[color:var(--color-priority-high)] mb-4">
            {rowError}
          </p>
        )}
        {rowNotice && !rowError && (
          <p role="status" className="text-sm text-mercury mb-4">
            {rowNotice}
          </p>
        )}
        {error ? (
          <ErrorState title="Staff accounts could not be loaded" message="Try again in a moment." onRetry={load} />
        ) : loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="w-5 h-5 animate-spin text-mercury" strokeWidth={1.75} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[760px]">
              <thead>
                <tr className="border-b border-line text-sm text-mercury">
                  <th className="py-3 pr-4 font-normal">Name</th>
                  <th className="py-3 pr-4 font-normal">Role and unit</th>
                  <th className="py-3 pr-4 font-normal">Station</th>
                  <th className="py-3 pr-4 font-normal">Open cases</th>
                  <th className="py-3 pr-4 font-normal">Last sign-in</th>
                  <th className="py-3 font-normal text-right">Access</th>
                </tr>
              </thead>
              <tbody>
                {staff.map((s) => (
                  <Fragment key={s.id}>
                    <tr className={`border-b border-line last:border-0 ${s.active ? "" : "opacity-55"}`}>
                      <td className="py-4 pr-4">
                        <p className="text-sm text-carbon">{s.name}</p>
                        <p className="text-xs text-mercury">{s.username ?? s.email}</p>
                      </td>
                      <td className="py-4 pr-4 text-sm text-carbon">
                        {s.role === "admin" ? "Administrator" : `Officer, ${s.unit ?? "general duty"}`}
                        {s.role === "officer" && s.availability && s.availability !== "available" && (
                          <span className="block text-xs text-mercury">{AVAILABILITY_LABEL[s.availability]}</span>
                        )}
                      </td>
                      <td className="py-4 pr-4 text-sm text-carbon">
                        {s.role === "officer" ? (
                          <>
                            {stationName(s.station) ?? <span className="text-mercury">Not set</span>}
                            <span className="block text-xs text-mercury tabular-nums">
                              capacity {s.capacity ?? 10}
                            </span>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-4 pr-4 text-sm text-carbon tabular-nums">
                        {s.role === "officer" ? s.open_cases : "—"}
                      </td>
                      <td className="py-4 pr-4 text-sm text-mercury whitespace-nowrap">
                        {s.last_login_at ? formatDateTime(toIsoUtc(s.last_login_at)) : "Never"}
                      </td>
                      <td className="py-4 text-right whitespace-nowrap">
                        <button
                          onClick={() => setEditingId(editingId === s.id ? null : s.id)}
                          aria-expanded={editingId === s.id}
                          className="px-4 py-2 rounded-full border border-line text-sm text-carbon hover:bg-vellum transition-colors mr-2"
                        >
                          {editingId === s.id ? "Close" : "Edit"}
                        </button>
                        {s.id === user?.id ? (
                          <span className="text-sm text-mercury">You</span>
                        ) : (
                          <button
                            onClick={() => toggleActive(s)}
                            disabled={pendingId === s.id}
                            className="px-4 py-2 rounded-full border border-line text-sm text-carbon hover:bg-vellum transition-colors disabled:opacity-40"
                          >
                            {s.active ? "Deactivate" : "Reactivate"}
                          </button>
                        )}
                      </td>
                    </tr>
                    {editingId === s.id && (
                      <EditStaffPanel
                        account={s}
                        stations={stations}
                        onClose={() => setEditingId(null)}
                        onSaved={(updated, notice) => {
                          setStaff((list) => list.map((x) => (x.id === updated.id ? updated : x)));
                          setRowNotice(notice);
                          setRowError(null);
                          setEditingId(null);
                        }}
                      />
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
