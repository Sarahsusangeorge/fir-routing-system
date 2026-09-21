import { motion } from "framer-motion";
import { Info } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import ErrorState from "../components/ErrorState";
import HistoryFilters, { type PriorityFilter, type SortKey } from "../components/HistoryFilters";
import HistoryTable from "../components/HistoryTable";
import SectionLabel from "../components/SectionLabel";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/useAuth";
import { fetchCases, fetchStaff, isDemoMode, type CaseScope } from "../services/api";
import { isOpenStatus, type Complaint, type StaffAccount } from "../types";

const PRIORITY_RANK: Record<Complaint["priority"]["level"], number> = { High: 3, Medium: 2, Low: 1 };

const SCOPES: { value: CaseScope; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "closed", label: "Closed" },
  { value: "all", label: "All" },
];

type OfficerFilter = "all" | "unassigned" | number;
type View = "mine" | "all";

export default function CasesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const navigate = useNavigate();
  const location = useLocation();
  const flash = (location.state as { flash?: string } | null)?.flash;

  const [cases, setCases] = useState<Complaint[]>([]);
  const [officers, setOfficers] = useState<StaffAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [scope, setScope] = useState<CaseScope>("open");
  const [view, setView] = useState<View>(isAdmin ? "all" : "mine");
  const [officer, setOfficer] = useState<OfficerFilter>("all");
  const [search, setSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("All");
  const [sortKey, setSortKey] = useState<SortKey>("priority");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    // Load the selected set once; the open/closed tabs and filters work on it.
    fetchCases("all", "all", view)
      .then((list) => {
        if (!cancelled) setCases(list);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    if (isAdmin) {
      fetchStaff()
        .then((staff) => {
          if (!cancelled) setOfficers(staff.filter((s) => s.role === "officer"));
        })
        .catch(() => undefined);
    }
    return () => {
      cancelled = true;
    };
  }, [isAdmin, view]);

  const reload = () => {
    setLoading(true);
    setError(false);
    fetchCases("all", "all", view)
      .then(setCases)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  const open = useMemo(() => cases.filter((c) => isOpenStatus(c.status)), [cases]);
  const stats = useMemo(
    () => ({
      open: open.length,
      toReview: open.filter((c) => (c.status ?? "New") === "New").length,
      investigating: open.filter((c) => c.status === "Under Investigation").length,
      high: open.filter((c) => c.priority.level === "High").length,
      unassigned: open.filter((c) => !c.assignment?.officer_id).length,
    }),
    [open]
  );

  const filtered = useMemo(() => {
    let list = cases;
    if (scope === "open") list = list.filter((c) => isOpenStatus(c.status));
    if (scope === "closed") list = list.filter((c) => !isOpenStatus(c.status));
    if (officer === "unassigned") list = list.filter((c) => !c.assignment?.officer_id);
    else if (officer !== "all") list = list.filter((c) => c.assignment?.officer_id === officer);
    if (priorityFilter !== "All") list = list.filter((c) => c.priority.level === priorityFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (c) =>
          c.complaint_text.toLowerCase().includes(q) ||
          c.sections.some((s) => s.code.toLowerCase().includes(q) || s.title.toLowerCase().includes(q)) ||
          c.routing.unit.toLowerCase().includes(q) ||
          (c.assignment?.officer_name ?? "").toLowerCase().includes(q) ||
          (c.complainant?.name ?? "").toLowerCase().includes(q) ||
          String(c.complaint_id).includes(q)
      );
    }
    const sorted = [...list];
    if (sortKey === "priority") {
      sorted.sort(
        (a, b) => PRIORITY_RANK[b.priority.level] - PRIORITY_RANK[a.priority.level] || b.priority.score - a.priority.score
      );
    } else if (sortKey === "date") {
      sorted.sort((a, b) => new Date(b.received_at).getTime() - new Date(a.received_at).getTime());
    } else {
      sorted.sort((a, b) => b.complaint_id - a.complaint_id);
    }
    return sorted;
  }, [cases, scope, officer, priorityFilter, search, sortKey]);

  const counts: Record<CaseScope, number> = {
    open: open.length,
    closed: cases.length - open.length,
    all: cases.length,
  };

  return (
    <div className="container-page pt-32 pb-24">
      <SectionLabel className="mb-6">{isAdmin ? "Case portal" : `${user?.name ?? ""}${user?.unit ? `, ${user.unit}` : ""}`}</SectionLabel>
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-[32px] md:text-[40px] font-light text-carbon max-w-2xl"
      >
        {isAdmin ? "All cases" : view === "mine" ? "Your cases" : "Every case"}
      </motion.h1>
      <p className="text-base text-mercury mt-4 max-w-xl">
        {isAdmin
          ? "Every complaint across all stations and units. Cases are allocated automatically by unit, station and workload; open one to reassign it."
          : view === "mine"
            ? "Complaints allocated to you, most urgent first. Open a case to review it, record your investigation and update the complainant."
            : "Every complaint in the district and who is handling it. You can read any case; only the officer it is allocated to can act on it."}
      </p>

      {isDemoMode() && (
        <p className="flex items-start gap-2 text-xs text-mercury mt-4 max-w-xl">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          Demo mode — every record below is synthetic, generated for demonstration only. None represent a real
          person, complaint, or case file.
        </p>
      )}

      {flash && (
        <p role="status" className="mt-6 max-w-xl text-sm text-carbon bg-paper border border-line rounded-[16px] px-5 py-4">
          {flash}
        </p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-10">
        <StatCard label="Open cases" value={stats.open} accent="neutral" />
        <StatCard label="Not yet reviewed" value={stats.toReview} accent="medium" delay={0.05} />
        <StatCard label="Under investigation" value={stats.investigating} accent="low" delay={0.1} />
        {isAdmin ? (
          <StatCard label="Unassigned" value={stats.unassigned} accent="high" delay={0.15} />
        ) : (
          <StatCard label="High priority" value={stats.high} accent="high" delay={0.15} />
        )}
      </div>

      <div className="bg-paper border border-line rounded-[24px] p-6 md:p-8 mt-10">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-1 bg-vellum rounded-full p-1" role="group" aria-label="Show cases">
            {SCOPES.map((s) => (
              <button
                key={s.value}
                onClick={() => setScope(s.value)}
                aria-pressed={scope === s.value}
                className={`px-4 py-2 rounded-full text-sm transition-colors ${
                  scope === s.value ? "bg-paper text-carbon shadow-[0_1px_2px_rgba(15,14,18,0.06)]" : "text-mercury hover:text-carbon"
                }`}
              >
                {s.label} <span className="tabular-nums text-mercury">{counts[s.value]}</span>
              </button>
            ))}
          </div>

          {!isAdmin && (
            <div className="flex items-center gap-1 bg-vellum rounded-full p-1" role="group" aria-label="Whose cases">
              {(["mine", "all"] as View[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  aria-pressed={view === v}
                  className={`px-4 py-2 rounded-full text-sm transition-colors ${
                    view === v ? "bg-paper text-carbon shadow-[0_1px_2px_rgba(15,14,18,0.06)]" : "text-mercury hover:text-carbon"
                  }`}
                >
                  {v === "mine" ? "My cases" : "All cases"}
                </button>
              ))}
            </div>
          )}

          {isAdmin && (
            <label className="flex items-center gap-2 text-sm text-mercury">
              Officer
              <select
                value={String(officer)}
                onChange={(e) => {
                  const v = e.target.value;
                  setOfficer(v === "all" || v === "unassigned" ? v : Number(v));
                }}
                className="pl-3 pr-8 py-2.5 rounded-full border border-line bg-paper text-carbon text-sm focus:outline-none focus:ring-2 focus:ring-carbon/30 max-w-[240px]"
              >
                <option value="all">Everyone</option>
                <option value="unassigned">Unassigned</option>
                {officers.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({o.open_cases} open){o.active ? "" : " (inactive)"}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        <HistoryFilters
          search={search}
          onSearchChange={setSearch}
          priorityFilter={priorityFilter}
          onPriorityFilterChange={setPriorityFilter}
          sortKey={sortKey}
          onSortKeyChange={setSortKey}
        />

        <div className="mt-8">
          {error ? (
            <ErrorState title="Cases could not be loaded" message="The case service could not be reached." onRetry={reload} />
          ) : (
            <HistoryTable
              complaints={filtered}
              loading={loading}
              showOfficer={isAdmin || view === "all"}
              onSelect={(c) => navigate(`/cases/${c.complaint_id}`)}
              emptyMessage={
                cases.length === 0
                  ? isAdmin || view === "all"
                    ? "No complaints have been filed yet."
                    : "No cases have been allocated to you yet."
                  : "No cases match your current filters."
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}
