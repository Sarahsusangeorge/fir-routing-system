# NIVARA: Council Verdict on Strengths, Weaknesses and Gaps (5 October 2026)

**Method.** Five independent advisors (Contrarian, First Principles, Expansionist, Outsider, Executor) each answered the question. Five anonymised peer reviews followed, then a synthesis. All five reviewers ranked the First Principles response strongest. Four of five ranked the Expansionist response as having the biggest blind spot.

## How it works now
A complaint narrative goes through these steps:

1. IPC sections are predicted. **This is a keyword stub; the DistilBERT weights are missing.**
2. Priority = statutory severity × confidence.
3. Routing uses a victim-centric rule table.
4. The case is allocated to the least-loaded suitable officer.
5. The case moves through a workflow the server enforces, with an audit trail.

There are three portals: citizen, officer and administrator.

## Agreed
- **The running artefact does not demonstrate the research claim.** Statute prediction driving the decisions is not shown: there is no reproducible accuracy, the stub fails on negation, and it misses offences without keywords.
- **Severity × confidence demotes exactly the cases the system understands least.** Uncertain-but-grave cases should be escalated, not demoted.
- **The legal base is out of date and unverified.** The system uses the IPC, which the BNS replaced in July 2024, and the cognizable and bailable values have not been checked.
- **The real strength is the accountability and workflow layer:**
  - enforced case states;
  - an audit trail;
  - "Not Registered" kept as an outcome the citizen can see;
  - transfers that require a stated reason;
  - restricted access to sexual-offence cases.

## Disputed
- **Product.** Is the product the pipeline (Expansionist) or a validated classifier (Contrarian, Executor)?
- **Framing.** Is statute-based triage even the right problem? First Principles argued the documented failure is refusal to register a complaint (*Lalita Kumari*, 2013). It also argued urgency comes from facts, not statutes: a missing person maps to no offence, yet is the most urgent case.

## Blind spots raised in peer review
- DPDP Act 2023: consent, retention and encryption.
- BNS s.72 (victim identity) applied to logs, backups and any training data.
- Officer-registered labels encode station bias.
- Complainants can game priority by adding trigger words.
- Officers may rubber-stamp suggestions (automation bias).
- Unequal access for low-literacy and non-English complainants.
- Ethics approval for any study.

## Recommendation
- Present NIVARA as **an accountability-first case workflow with a statute-assisted triage layer that a human checks**.
- Make triage urgency-first: escalate uncertain-but-grave cases.
- Label the stub honestly as a rule-based baseline.
- Measure routing correctness on a small labelled set mapped to the BNS.

## First action
Find the DistilBERT weights and their evaluation data today. If they're found, add them with a checksum and reproduce the reported numbers. If not, remove the F1 claims.
