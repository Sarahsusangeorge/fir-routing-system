# NIVARA — Experiment results

Status as of **12 October 2026**, against `main` at `918ebe0`. This file
holds the results generated so far and lists those still needed. The paper's
results section should be written from this file and nothing else.

## Results still needed

These must come from the Track A model work; nothing below substitutes for
them. The audit's review council put this first among all open items.

- **Section classification (DistilBERT, 100 IPC labels, ILSI):** micro-F1,
  macro-F1, precision, recall; ideally per-label F1 for frequent sections.
  The deployed configuration is a sigmoid threshold of 0.2, 256-token input,
  at most 4 sections returned.
- **Baseline:** TF-IDF + Random Forest on the same split and label set.
- **Training setup:** data split, epochs, learning rate, batch size,
  hardware, training time.
- **Model artefact:** the weights are not in the repository. Add them with a
  checksum (release asset or Git LFS) so the numbers can be reproduced; if
  they cannot be recovered, remove every accuracy claim and present the
  keyword baseline honestly as a rule-based system.
- **Optional:** API latency with the model loaded on CPU, and routing
  correctness on a small labelled set.

Until then, **the classification claim is undemonstrated**: the keyword
baseline (22 IPC sections) is what runs.

## Experiment 1: Workload-aware officer allocation (simulation)

### Question

Does NIVARA's allocation rule (`workflow.rank_officers`) distribute
complaints better than the simple strategies a police system might otherwise
use?

### Method

- Script: `backend/experiments/allocation_sim.py`, which calls the production
  ranking function unchanged. Reproduce with
  `python experiments/allocation_sim.py --runs 30`.
- **Officers:** 25 across 4 stations. Per station: 2 Local Police Station
  officers, 1 each for Crime Branch, Economic Offences Wing and Women & Child
  Protection Unit, 1 general-duty officer. Cyber Cell specialists exist at one
  station only (a deliberate staffing gap). Capacities uniform on 6–14. Each
  run has 10% of officers on leave and 15% marked busy.
- **Complaints:** 600 per run, one per time step. Unit mix: Local Police
  Station 45%, Crime Branch 12%, Economic Offences Wing 15%, Women & Child
  Protection 15%, Cyber Cell 13%. Priority mix: High 20%, Medium 50%, Low
  30%. Station uniform. Each open case closes with probability 0.025 per step.
- **Strategies:** NIVARA (tier + weighted load ÷ capacity + busy penalty);
  round-robin; least open cases (unweighted, ignoring capacity, station and
  availability); random.
- **Fairness controls:** identical eligibility rule, officers, complaint
  stream and closures for every strategy; runs paired by seed.
- **30 runs**, reported as mean ± standard deviation. Paired Wilcoxon
  signed-rank tests compare NIVARA with each alternative (* = p < 0.05).
- **Load weighting:** High 3, Medium 2, Low 1 capacity units per open case.

### Results: comparison with baselines

| Metric | Better | **NIVARA** | Round-robin | Least open cases | Random |
|---|---|---|---|---|---|
| Assignments that push an officer over capacity (%) | lower | 6.90 ± 2.71 | 9.97 ± 5.00 | 7.27 ± 4.80 | 14.11 ± 4.90 |
| Most-loaded officer, mean over time (% of capacity) | lower | 104.03 ± 9.48 | 116.02 ± 20.74 | 107.77 ± 23.32 | 128.25 ± 20.56 |
| Imbalance of load across officers at the end (CV) | lower | 0.89 ± 0.11 | 0.96 ± 0.21 | 0.86 ± 0.22 | 1.02 ± 0.17 |
| Assignments given to officers marked busy (%) | lower | 12.43 ± 6.47 | 16.43 ± 8.06 | 16.49 ± 8.15 | 16.47 ± 8.46 |
| Cases handled at the station where they were filed (%) | higher | 87.16 ± 3.70 | 24.83 ± 2.08 | 24.86 ± 2.09 | 25.06 ± 2.09 |
| Cases handled by a specialist of the right unit (%) | higher | 97.03 ± 3.55 | 98.73 ± 3.82 | 98.73 ± 3.82 | 98.73 ± 3.82 |

Wilcoxon p-values, NIVARA vs each baseline:

| Metric | round_robin | least_cases | random |
|---|---|---|---|
| Over-capacity assignments | 3.3e-04 * | 6.6e-01 | 1.7e-06 * |
| Peak load | 9.2e-06 * | 7.6e-01 | 1.9e-09 * |
| Load imbalance (CV) | 5.5e-02 | 6.7e-02 | 1.4e-04 * |
| Assignments to busy officers | 4.3e-06 * | 8.1e-06 * | 1.0e-05 * |
| Local-station handling | 1.7e-06 * | 1.7e-06 * | 1.7e-06 * |
| Specialist handling | 1.2e-05 * | 1.2e-05 * | 1.2e-05 * |

### Results: ablation (one component removed)

| Metric | Better | **Full NIVARA** | No station preference | No capacity | No priority weights | No busy penalty |
|---|---|---|---|---|---|---|
| Assignments that push an officer over capacity (%) | lower | 6.90 ± 2.71 | 5.22 ± 3.73 | 8.89 ± 4.00 | 7.09 ± 2.63 | 6.55 ± 2.45 |
| Most-loaded officer, mean over time (% of capacity) | lower | 104.03 ± 9.48 | 98.24 ± 20.75 | 113.23 ± 15.71 | 105.37 ± 9.26 | 102.62 ± 8.42 |
| Imbalance of load across officers at the end (CV) | lower | 0.89 ± 0.11 | 0.84 ± 0.14 | 0.93 ± 0.13 | 0.88 ± 0.12 | 0.89 ± 0.12 |
| Assignments given to officers marked busy (%) | lower | 12.43 ± 6.47 | 5.90 ± 4.60 | 12.52 ± 6.33 | 12.68 ± 6.47 | 16.29 ± 8.00 |
| Cases handled at the station where they were filed (%) | higher | 87.16 ± 3.70 | 25.17 ± 1.33 | 87.53 ± 3.93 | 87.19 ± 3.71 | 87.61 ± 3.55 |
| Cases handled by a specialist of the right unit (%) | higher | 97.03 ± 3.55 | 98.38 ± 3.76 | 96.97 ± 3.38 | 96.97 ± 3.57 | 97.14 ± 3.63 |

Wilcoxon p-values, full NIVARA vs each ablation:

| Metric | no_station | no_capacity | no_priority | no_busy |
|---|---|---|---|---|
| Over-capacity assignments | 4.2e-03 * | 3.2e-04 * | 2.4e-01 | 2.8e-02 * |
| Peak load | 5.5e-02 | 1.3e-08 * | 8.1e-03 * | 9.3e-03 * |
| Load imbalance (CV) | 1.4e-02 * | 2.0e-01 | 7.5e-01 | 5.2e-01 |
| Assignments to busy officers | 2.6e-06 * | 6.8e-01 | 3.4e-02 * | 1.7e-06 * |
| Local-station handling | 1.9e-09 * | 1.1e-01 | 6.3e-01 | 1.9e-02 * |
| Specialist handling | 1.2e-05 * | 5.2e-01 | 5.2e-01 | 8.6e-01 |

### Interpretation

1. **Locality is the largest effect.** NIVARA keeps 87% of complaints at the
   station where they were filed, against about 25% for every baseline
   (chance level with four stations). Removing the station term drops this to
   25%, confirming the station tier is responsible.
2. **Load protection matches the best baseline and is more stable.**
   Over-capacity assignments (6.9%) and peak load (104%) are significantly
   better than round-robin (p < 0.001) and random (p < 0.001), and statistically indistinguishable
   from least-open-cases (p = 0.66, p = 0.76), while locality is about 3.5×
   higher. The standard deviation of peak load is less than half that of the
   baselines (9.5 vs 20–23), so worst cases are milder and more predictable.
3. **Capacity awareness matters.** Treating every officer as average raises
   over-capacity assignments from 6.9% to 8.9% and peak load from 104% to
   113% (both p < 0.001).
4. **The busy penalty works.** Assignments to officers marked busy fall from
   about 16% to 12.4% (p < 0.001 against every baseline and against the
   ablation without the penalty).
5. **Priority weighting has little effect under this mix**: over-capacity
   assignments change by 0.2 points (p = 0.24), though peak load differs
   slightly (105.4% vs 104.0%, p = 0.008). Report this honestly: its value is in making capacity reflect
   effort, and it may matter more with a higher share of grave cases.

### Trade-offs to report

- **Locality versus balance.** Removing the station preference lowers
  over-capacity assignments (6.9% → 5.2%, p = 0.004), assignments to busy
  officers (12.4% → 5.9%, p < 0.001) and imbalance (0.89 → 0.84, p = 0.014). Keeping complaints local costs
  some load balance; the weights are policy choices a jurisdiction can tune.
- **Specialisation versus load.** NIVARA gives 97.0% of cases to a specialist
  of the right unit, against 98.7% for baselines that always pick a
  specialist when one is free, because an overloaded specialist elsewhere can
  rank below a free general-duty officer at the case's station. Intended, but
  a cost to state.
- **Imbalance (CV) is high for every strategy** (0.84–1.02), because
  specialists and general-duty officers receive very different volumes by
  design. Reported for completeness, not as a target.

### Limitations

- Synthetic workload: unit mix, priority mix, capacities and closure rate are
  assumptions, not measured police data.
- Closure is random and independent of priority or officer.
- Officer availability is fixed within a run.
- One scenario family (4 stations, 25 officers); scaling untested.

### Reproduction

Re-run on 12 October 2026 against the post-audit code (`918ebe0`): every
figure above is **identical** to the 21 September run, confirming the audit
did not alter allocation behaviour. Output files: `allocation_comparison.csv`,
`allocation_ablation.csv`, `allocation_significance.csv`,
`allocation_output.txt`, `fig_allocation_results.png`.

## Experiment 2: Functional and security verification

**Backend:** `pytest` suite in `backend/tests/` (isolated temporary databases
via `NIVARA_DB_PATH`, synthetic data), including the two original scripts.
Verified independently on 12 October 2026:

```
216 passed, 1 xfailed in 30.16s
```

The single expected failure is declared and explained:
`test_stub_understands_negation` — "Known limitation of the keyword stub: it
does not understand negation." It documents a real weakness of the fallback
classifier rather than hiding a defect.

**Frontend:** Vitest, verified the same day: **15 tests, all passing**.

**Regression value.** 41 of these tests failed against the pre-audit code
(evidence in `audit/evidence/01`), so the suite demonstrably catches the
defects it was written for.

**Other evidence** in `audit/evidence/`: Bandit, Ruff, pip-audit, npm audit,
a secret scan, axe-core accessibility scans (0 violations on scanned pages)
and latency measurements (p95 ≤ 28 ms locally, keyword classifier). Note that
no CI workflow is committed, so these run only when someone runs them.

## Experiment 3 (not yet run): routing correctness

The council recommended measuring routing correctness on a small labelled set
mapped to the BNS. Not started; it would need a few hundred narratives with
agreed unit labels, and would give the paper a second measured result that
does not depend on the missing model weights.
