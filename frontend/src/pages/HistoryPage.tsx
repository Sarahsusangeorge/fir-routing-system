import { motion } from "framer-motion";
import { Info } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import ComplaintDetailDrawer from "../components/ComplaintDetailDrawer";
import ErrorState from "../components/ErrorState";
import HistoryFilters, { type PriorityFilter, type SortKey } from "../components/HistoryFilters";
import HistoryTable from "../components/HistoryTable";
import SectionLabel from "../components/SectionLabel";
import StatCard from "../components/StatCard";
import { fetchComplaints, isDemoMode } from "../services/api";
import type { Complaint } from "../types";

const PRIORITY_RANK: Record<Complaint["priority"]["level"], number> = { High: 3, Medium: 2, Low: 1 };

export default function HistoryPage() {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("All");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [selected, setSelected] = useState<Complaint | null>(null);

  const load = () => {
    setLoading(true);
    setError(false);
    fetchComplaints()
      .then(setComplaints)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const stats = useMemo(
    () => ({
      total: complaints.length,
      high: complaints.filter((c) => c.priority.level === "High").length,
      medium: complaints.filter((c) => c.priority.level === "Medium").length,
      low: complaints.filter((c) => c.priority.level === "Low").length,
    }),
    [complaints]
  );

  const filtered = useMemo(() => {
    let list = complaints;
    if (priorityFilter !== "All") {
      list = list.filter((c) => c.priority.level === priorityFilter);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (c) =>
          c.complaint_text.toLowerCase().includes(q) ||
          c.sections.some((s) => s.code.toLowerCase().includes(q) || s.title.toLowerCase().includes(q)) ||
          c.routing.unit.toLowerCase().includes(q) ||
          String(c.complaint_id).includes(q)
      );
    }

    const sorted = [...list];
    if (sortKey === "priority") {
      sorted.sort((a, b) => PRIORITY_RANK[b.priority.level] - PRIORITY_RANK[a.priority.level] || b.priority.score - a.priority.score);
    } else if (sortKey === "date") {
      sorted.sort((a, b) => new Date(b.received_at).getTime() - new Date(a.received_at).getTime());
    } else {
      sorted.sort((a, b) => b.complaint_id - a.complaint_id);
    }
    return sorted;
  }, [complaints, priorityFilter, search, sortKey]);

  return (
    <div className="container-page pt-32 pb-24">
      <SectionLabel className="mb-6">History</SectionLabel>
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-[32px] font-normal text-carbon max-w-2xl"
      >
        Complaint history
      </motion.h1>
      <p className="text-base text-mercury mt-4 max-w-xl">Previously analyzed complaints and routing outcomes.</p>

      {isDemoMode() && (
        <p className="flex items-start gap-2 text-xs text-mercury mt-4 max-w-xl">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          Demo mode — every record below is synthetic, generated for demonstration only. None represent a real
          person, complaint, or case file.
        </p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-12">
        <StatCard label="Total complaints" value={stats.total} accent="neutral" />
        <StatCard label="High priority" value={stats.high} accent="high" delay={0.05} />
        <StatCard label="Medium priority" value={stats.medium} accent="medium" delay={0.1} />
        <StatCard label="Low priority" value={stats.low} accent="low" delay={0.15} />
      </div>

      <div className="bg-paper border border-line rounded-[24px] p-6 md:p-8 mt-10">
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
            <ErrorState
              title="Unable to load complaint history"
              message="The complaint history service could not be reached."
              onRetry={load}
            />
          ) : (
            <HistoryTable complaints={filtered} onSelect={setSelected} loading={loading} />
          )}
        </div>
      </div>

      <ComplaintDetailDrawer complaint={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
