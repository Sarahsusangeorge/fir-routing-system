import { Search } from "lucide-react";
import type { PriorityLevel } from "../types";

export type SortKey = "priority" | "date" | "id";
export type PriorityFilter = "All" | PriorityLevel;

interface HistoryFiltersProps {
  search: string;
  onSearchChange: (v: string) => void;
  priorityFilter: PriorityFilter;
  onPriorityFilterChange: (v: PriorityFilter) => void;
  sortKey: SortKey;
  onSortKeyChange: (v: SortKey) => void;
}

const PRIORITY_OPTIONS: PriorityFilter[] = ["All", "High", "Medium", "Low"];
const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "priority", label: "Priority" },
  { value: "date", label: "Date" },
  { value: "id", label: "Complaint ID" },
];

export default function HistoryFilters({
  search,
  onSearchChange,
  priorityFilter,
  onPriorityFilterChange,
  sortKey,
  onSortKeyChange,
}: HistoryFiltersProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center gap-4 md:gap-6">
      <div className="relative flex-1">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-mercury" strokeWidth={1.75} aria-hidden="true" />
        <input
          type="search"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search complaints"
          aria-label="Search complaints"
          className="w-full pl-11 pr-4 py-3 rounded-full border border-line bg-paper text-sm text-carbon placeholder:text-mercury focus:outline-none focus:ring-2 focus:ring-carbon/30 focus:border-carbon/40 transition-colors"
        />
      </div>

      <div className="flex items-center gap-1 bg-paper border border-line rounded-full p-1" role="group" aria-label="Filter by priority">
        {PRIORITY_OPTIONS.map((opt) => (
          <button
            key={opt}
            onClick={() => onPriorityFilterChange(opt)}
            aria-pressed={priorityFilter === opt}
            className={`px-3.5 py-1.5 rounded-full text-sm transition-colors ${
              priorityFilter === opt ? "bg-carbon text-vellum" : "text-mercury hover:text-carbon"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-2 text-sm text-mercury">
        Sort by
        <select
          value={sortKey}
          onChange={(e) => onSortKeyChange(e.target.value as SortKey)}
          className="pl-3 pr-8 py-2.5 rounded-full border border-line bg-paper text-carbon text-sm focus:outline-none focus:ring-2 focus:ring-carbon/30"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
