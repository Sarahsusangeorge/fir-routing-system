"""
Allocation experiment: NIVARA's officer ranking against simpler strategies.

This runs the real allocation function (workflow.rank_officers) on a
simulated stream of complaints and compares it with three baselines that
police systems commonly use or that a naive implementation would use:

  round_robin    cycle through the eligible officers of the unit in turn
  least_cases    the eligible officer with the fewest open cases (a plain
                 count: ignores capacity, priority, station and "busy")
  random         a uniformly random eligible officer

Every strategy sees the same officers, the same complaints and the same
closures, and every strategy respects the same eligibility rule (officers
of the case's unit first, general-duty officers only if the unit has none
available; officers on leave are never chosen). Differences between the
strategies therefore come only from how they choose among eligible
officers.

The workload is synthetic. The unit mix, priority mix and closure rate are
stated below as parameters, so the experiment can be rerun with other
assumptions. The results describe the allocation method, not the
classifier, and should be reported as a simulation.

Run:
    python experiments/allocation_sim.py            # 30 runs, prints a table
    python experiments/allocation_sim.py --runs 100 --csv results.csv
"""

import argparse
import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workflow  # noqa: E402

# ---------------------------------------------------------------------------
# Scenario parameters
# ---------------------------------------------------------------------------

STATIONS = ["PS-CENTRAL", "PS-NORTH", "PS-SOUTH", "PS-EAST"]

# Specialist officers per unit at each station (general duty added separately).
UNIT_STAFFING = {
    "Local Police Station": 2,
    "Crime Branch": 1,
    "Economic Offences Wing": 1,
    "Women & Child Protection Unit": 1,
}
# Cyber Cell has specialists at one station only, so most cyber cases must
# be handled across stations or by general duty: a realistic staffing gap.
CYBER_STATION = "PS-CENTRAL"
GENERAL_DUTY_PER_STATION = 1

CAPACITY_RANGE = (6, 14)       # officers differ in how much they can carry
P_ON_LEAVE = 0.10              # share of officers on leave in a run
P_BUSY = 0.15                  # share marked busy

UNIT_MIX = {                   # share of incoming complaints by unit
    "Local Police Station": 0.45,
    "Crime Branch": 0.12,
    "Economic Offences Wing": 0.15,
    "Women & Child Protection Unit": 0.15,
    "Cyber Cell": 0.13,
}
PRIORITY_MIX = {"High": 0.20, "Medium": 0.50, "Low": 0.30}

N_CASES = 600                  # complaints arriving, one per time step
P_CLOSE_PER_STEP = 0.025       # chance an open case is closed at each step


def build_officers(rng):
    officers, next_id = [], 1
    for station in STATIONS:
        staffing = dict(UNIT_STAFFING)
        if station == CYBER_STATION:
            staffing["Cyber Cell"] = 1
        for unit, count in staffing.items():
            for _ in range(count):
                officers.append({"id": next_id, "unit": unit, "station": station})
                next_id += 1
        for _ in range(GENERAL_DUTY_PER_STATION):
            officers.append({"id": next_id, "unit": None, "station": station})
            next_id += 1
    for o in officers:
        o["capacity"] = rng.randint(*CAPACITY_RANGE)
        roll = rng.random()
        o["availability"] = "on_leave" if roll < P_ON_LEAVE else "busy" if roll < P_ON_LEAVE + P_BUSY else "available"
        o["active"] = True
    return officers


def build_cases(rng):
    units, unit_w = zip(*UNIT_MIX.items())
    prios, prio_w = zip(*PRIORITY_MIX.items())
    return [
        {
            "unit": rng.choices(units, unit_w)[0],
            "priority": rng.choices(prios, prio_w)[0],
            "station": rng.choice(STATIONS),
        }
        for _ in range(N_CASES)
    ]


def eligible(officers, unit):
    """Same eligibility for every strategy: unit first, then general duty."""
    pool = [o for o in officers if o["availability"] != "on_leave"]
    in_unit = [o for o in pool if o["unit"] == unit]
    return in_unit or [o for o in pool if o["unit"] is None]


# ---------------------------------------------------------------------------
# Strategies. Each takes (officers with live metrics, case, state, rng) and
# returns an officer id or None.
# ---------------------------------------------------------------------------

def nivara(officers, case, state, rng):
    return workflow.choose_officer(officers, case["unit"], case["station"])


def round_robin(officers, case, state, rng):
    pool = sorted(eligible(officers, case["unit"]), key=lambda o: o["id"])
    if not pool:
        return None
    key = case["unit"] if pool[0]["unit"] == case["unit"] else "general"
    i = state.setdefault(key, 0)
    state[key] = i + 1
    return pool[i % len(pool)]["id"]


def least_cases(officers, case, state, rng):
    pool = eligible(officers, case["unit"])
    return min(pool, key=lambda o: (o["open_cases"], o["id"]))["id"] if pool else None


def random_choice(officers, case, state, rng):
    pool = eligible(officers, case["unit"])
    return rng.choice(pool)["id"] if pool else None


STRATEGIES = {
    "nivara": nivara,
    "round_robin": round_robin,
    "least_cases": least_cases,
    "random": random_choice,
}


# ---------------------------------------------------------------------------
# Ablations: NIVARA with one component switched off at a time, to show what
# each part of the ranking contributes.
# ---------------------------------------------------------------------------

def _ablated(transform, case_station=True):
    def strategy(officers, case, state, rng):
        view = [transform(dict(o)) for o in officers]
        return workflow.choose_officer(view, case["unit"], case["station"] if case_station else None)
    return strategy


def _no_capacity(o):
    o["capacity"] = sum(CAPACITY_RANGE) / 2          # everyone treated as average
    return o


def _no_priority_weight(o):
    o["weighted_load"] = o["open_cases"] * 2.0       # every case counts the same
    return o


def _no_busy_penalty(o):
    if o["availability"] == "busy":
        o["availability"] = "available"
    return o


ABLATIONS = {
    "nivara": nivara,
    "no_station": _ablated(lambda o: o, case_station=False),
    "no_capacity": _ablated(_no_capacity),
    "no_priority": _ablated(_no_priority_weight),
    "no_busy": _ablated(_no_busy_penalty),
}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate(strategy, officers_template, cases, seed):
    rng = random.Random(seed)            # same closures for every strategy
    officers = [dict(o) for o in officers_template]
    by_id = {o["id"]: o for o in officers}
    open_cases = []                      # (officer_id, priority)
    state = {}
    stats = {"assigned": 0, "unassigned": 0, "station_match": 0, "unit_match": 0,
             "overload": 0, "to_busy": 0, "peak_load": []}

    def refresh():
        for o in officers:
            mine = [p for oid, p in open_cases if oid == o["id"]]
            o["open_cases"] = len(mine)
            o["weighted_load"] = sum(workflow.case_weight(p) for p in mine)
            o.setdefault("last_assigned_at", None)

    for step, case in enumerate(cases):
        # Closures happen before the next arrival, identically across strategies.
        open_cases = [c for c in open_cases if rng.random() >= P_CLOSE_PER_STEP]
        refresh()

        oid = strategy(officers, case, state, rng)
        if oid is None:
            stats["unassigned"] += 1
            continue
        o = by_id[oid]
        stats["assigned"] += 1
        stats["station_match"] += o["station"] == case["station"]
        stats["unit_match"] += o["unit"] == case["unit"]
        stats["to_busy"] += o["availability"] == "busy"
        after = (o["weighted_load"] + workflow.case_weight(case["priority"])) / o["capacity"]
        stats["overload"] += after > 1.0
        o["last_assigned_at"] = f"{step:08d}"
        open_cases.append((oid, case["priority"]))

        refresh()
        working = [x for x in officers if x["availability"] != "on_leave"]
        ratios = [x["weighted_load"] / x["capacity"] for x in working]
        stats["peak_load"].append(max(ratios))

    working = [x for x in officers if x["availability"] != "on_leave"]
    ratios = [x["weighted_load"] / x["capacity"] for x in working]
    mean_ratio = statistics.mean(ratios)
    n = max(stats["assigned"], 1)
    return {
        "station_match_pct": 100 * stats["station_match"] / n,
        "specialist_pct": 100 * stats["unit_match"] / n,
        "overload_pct": 100 * stats["overload"] / n,
        "to_busy_pct": 100 * stats["to_busy"] / n,
        "mean_peak_load_pct": 100 * statistics.mean(stats["peak_load"]),
        "final_load_cv": statistics.pstdev(ratios) / mean_ratio if mean_ratio else 0.0,
        "unassigned": stats["unassigned"],
    }


METRICS = [
    ("overload_pct", "Assignments that push an officer over capacity (%)", "lower"),
    ("mean_peak_load_pct", "Most-loaded officer, mean over time (% of capacity)", "lower"),
    ("final_load_cv", "Imbalance of load across officers at the end (CV)", "lower"),
    ("to_busy_pct", "Assignments given to officers marked busy (%)", "lower"),
    ("station_match_pct", "Cases handled at the station where they were filed (%)", "higher"),
    ("specialist_pct", "Cases handled by a specialist of the right unit (%)", "higher"),
]


def run(runs, strategies=STRATEGIES, base_seed=2026):
    results = {name: {m: [] for m, _, _ in METRICS} for name in strategies}
    for r in range(runs):
        seed = base_seed + r
        rng = random.Random(seed)
        officers = build_officers(rng)
        cases = build_cases(rng)
        for name, fn in strategies.items():
            out = simulate(fn, officers, cases, seed=seed * 7 + 1)
            for m, _, _ in METRICS:
                results[name][m].append(out[m])
    return results


def summarise(results):
    rows = []
    for m, label, better in METRICS:
        row = {"metric": label, "better": better}
        for name in results:
            vals = results[name][m]
            row[name] = (statistics.mean(vals), statistics.pstdev(vals))
        rows.append(row)
    return rows


def print_table(title, rows, names):
    print(title)
    print(f"{'Metric':<58}" + "".join(f"{n:>18}" for n in names))
    for row in rows:
        cells = "".join(f"{row[n][0]:>11.2f} ± {row[n][1]:<5.2f}" for n in names)
        print(f"{row['metric'][:57]:<58}{cells}")
    print()


def write_csv(path, rows, names):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "better"] + [f"{n}_{s}" for n in names for s in ("mean", "sd")])
        for row in rows:
            w.writerow([row["metric"], row["better"]] +
                       [f"{v:.4f}" for n in names for v in row[n]])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--csv", help="write the comparison table to this CSV file")
    parser.add_argument("--ablation-csv", help="write the ablation table to this CSV file")
    args = parser.parse_args()

    print(f"{args.runs} runs, {N_CASES} complaints each, "
          f"{len(build_officers(random.Random(0)))} officers across {len(STATIONS)} stations\n")

    comparison = summarise(run(args.runs, STRATEGIES))
    print_table("Comparison with baseline strategies", comparison, list(STRATEGIES))

    ablation = summarise(run(args.runs, ABLATIONS))
    print_table("Ablation: NIVARA with one component removed", ablation, list(ABLATIONS))

    if args.csv:
        write_csv(args.csv, comparison, list(STRATEGIES))
    if args.ablation_csv:
        write_csv(args.ablation_csv, ablation, list(ABLATIONS))


if __name__ == "__main__":
    main()
