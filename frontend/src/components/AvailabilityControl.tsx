import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../context/useAuth";
import { setAvailability } from "../services/api";
import type { OfficerAvailability } from "../types";

const OPTIONS: { value: OfficerAvailability; label: string; help: string }[] = [
  { value: "available", label: "Available", help: "New cases can be allocated to you." },
  { value: "busy", label: "Busy", help: "You stay eligible, but other officers are preferred." },
  { value: "on_leave", label: "On leave", help: "No new cases, and your open cases move to colleagues." },
];

/**
 * Lets an officer say whether they can take work.
 *
 * The allocation rule already reads this: "busy" adds a penalty to an
 * officer's score, and "on leave" takes them out of the eligible pool
 * altogether and redistributes what they are holding. Without a control the
 * value could only ever be changed by an administrator, which defeats the
 * purpose of having it.
 */
export default function AvailabilityControl() {
  const { user, updateUser } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (user?.role !== "officer") return null;

  const current: OfficerAvailability = user.availability ?? "available";

  const choose = async (value: OfficerAvailability) => {
    if (value === current || busy) return;
    if (value === "on_leave" && !window.confirm("Go on leave? Your open cases will move to other officers.")) {
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await setAvailability(value);
      updateUser(result.user);
      setNotice(
        result.cases_moved
          ? `${result.cases_moved} open case${result.cases_moved === 1 ? "" : "s"} moved to other officers.`
          : null
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your availability could not be changed.");
    } finally {
      setBusy(false);
    }
  };

  const help = OPTIONS.find((o) => o.value === current)?.help;

  return (
    <div className="bg-paper border border-line rounded-[18px] p-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <span className="text-sm font-medium text-carbon">Your availability</span>
        <div role="group" aria-label="Your availability" className="flex flex-wrap gap-2">
          {OPTIONS.map((option) => {
            const active = option.value === current;
            return (
              <button
                key={option.value}
                onClick={() => choose(option.value)}
                disabled={busy}
                aria-pressed={active}
                className={`px-4 py-2 rounded-full text-sm border transition-colors disabled:opacity-40 ${
                  active
                    ? "bg-carbon text-vellum border-carbon"
                    : "border-line text-carbon hover:bg-vellum"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        {busy && <Loader2 className="w-4 h-4 animate-spin text-mercury" strokeWidth={1.75} />}
      </div>

      <p className="text-xs text-mercury mt-3">{help}</p>
      {notice && (
        <p role="status" className="text-xs text-mercury mt-2">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="text-xs text-[color:var(--color-priority-high)] mt-2">
          {error}
        </p>
      )}
    </div>
  );
}
