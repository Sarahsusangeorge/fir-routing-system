import {
  FINAL_STATUSES,
  NOTE_REQUIRED_STATUSES,
  isOpenStatus,
  type Assignment,
  type CitizenComplaint,
  type Complaint,
  type ComplaintEvent,
  type ComplaintStatus,
  type NewStaffAccount,
  type ReviewInfo,
  type ReviewRequest,
  type StaffAccount,
} from "../types";
import { DEMO_USERS, currentDemoRole } from "./auth";
import { ApiRequestError, apiFetch, AuthError, isDemoMode, NetworkError } from "./http";
import { classifyLocally } from "./localClassifier";
import { MOCK_COMPLAINTS } from "./mockData";

export { isDemoMode };

export class ClassificationError extends Error {}

export type CaseScope = "open" | "closed" | "all";

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * The backend stores timestamps as "YYYY-MM-DD HH:MM:SS" in UTC (SQLite's
 * datetime('now')). Adding the "Z" makes browsers read them as UTC and show
 * the viewer's local time, rather than treating them as local time.
 */
export function toIsoUtc(value: string): string;
export function toIsoUtc(value: string | null): string | null;
export function toIsoUtc(value: string | null): string | null {
  if (!value) return value;
  return /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value) ? `${value.replace(" ", "T")}Z` : value;
}

/**
 * Adapts a raw backend response into the shape the UI relies on, without
 * requiring any change to the backend's own contract:
 *  - `complaint_text` may be missing, so it's filled in from the text sent.
 *  - `explanation` defaults to an empty array rather than undefined.
 *  - timestamps are normalized with toIsoUtc.
 */
function normalizeComplaint(raw: Complaint, fallbackText?: string): Complaint {
  return {
    ...raw,
    complaint_text: raw.complaint_text || fallbackText || "",
    explanation: raw.explanation ?? [],
    received_at: toIsoUtc(raw.received_at),
    review: raw.review && {
      ...raw.review,
      reviewed_at: toIsoUtc(raw.review.reviewed_at),
      signature_confirmed_at: toIsoUtc(raw.review.signature_confirmed_at),
      signature_due_at: toIsoUtc(raw.review.signature_due_at),
    },
    assignment: raw.assignment && { ...raw.assignment, assigned_at: toIsoUtc(raw.assignment.assigned_at) },
    events: raw.events?.map((e) => ({ ...e, created_at: toIsoUtc(e.created_at) })),
  };
}

function normalizeCitizenComplaint(raw: CitizenComplaint): CitizenComplaint {
  return {
    ...raw,
    received_at: toIsoUtc(raw.received_at),
    signature_due_at: toIsoUtc(raw.signature_due_at),
    signature_confirmed_at: toIsoUtc(raw.signature_confirmed_at),
  };
}

function messageFrom(err: unknown, fallback: string): string {
  if (err instanceof AuthError || err instanceof ApiRequestError || err instanceof NetworkError) return err.message;
  return fallback;
}

// ---------------------------------------------------------------------------
// Filing a complaint at the station
// ---------------------------------------------------------------------------

export async function classifyComplaint(complaintText: string): Promise<Complaint> {
  const trimmed = complaintText.trim();
  if (!trimmed) {
    throw new ClassificationError("Complaint text is required");
  }

  if (!isDemoMode()) {
    try {
      return normalizeComplaint(
        await apiFetch<Complaint>("/api/classify", {
          method: "POST",
          body: JSON.stringify({ complaint_text: trimmed }),
        }),
        trimmed
      );
    } catch (err) {
      // Only an unreachable backend falls back to the local classifier. A
      // rejected request (bad input, expired session) is reported as is.
      if (!(err instanceof NetworkError)) {
        throw new ClassificationError(messageFrom(err, "The classification service could not be reached."));
      }
    }
  }

  // Demo mode: simulate latency and classify locally.
  await wait(600 + Math.random() * 400);
  return demoFile(trimmed, "officer");
}

// ---------------------------------------------------------------------------
// Case portal
// ---------------------------------------------------------------------------

/**
 * Cases from the portal. view="mine" is the officer's own caseload;
 * view="all" is every case in the district, which any officer may read.
 */
export async function fetchCases(
  scope: CaseScope = "all",
  officer: "all" | "unassigned" | number = "all",
  view: "mine" | "all" = "all"
): Promise<Complaint[]> {
  if (!isDemoMode()) {
    const params = new URLSearchParams({ limit: "200", scope });
    if (view === "mine") params.set("view", "mine");
    else if (officer !== "all") params.set("officer", String(officer));
    try {
      const data = await apiFetch<{ complaints: Complaint[] }>(`/api/complaints?${params}`);
      return data.complaints.map((c) => normalizeComplaint(c));
    } catch (err) {
      // A rejected request must not be papered over with demo data.
      if (!(err instanceof NetworkError)) throw err;
    }
  }

  await wait(350);
  return demoComplaints.filter((c) => {
    if (view === "mine" && c.assignment?.officer_id !== DEMO_USERS.officer.id) return false;
    if (officer === "unassigned" && c.assignment?.officer_id) return false;
    if (typeof officer === "number" && c.assignment?.officer_id !== officer) return false;
    if (scope === "open" && !isOpenStatus(c.status)) return false;
    if (scope === "closed" && isOpenStatus(c.status)) return false;
    return true;
  });
}

export async function fetchCase(id: number): Promise<Complaint> {
  if (!isDemoMode()) {
    return normalizeComplaint(await apiFetch<Complaint>(`/api/complaints/${id}`));
  }
  const found = demoComplaints.find((c) => c.complaint_id === id);
  if (!found) throw new ApiRequestError("Case not found", 404);
  return withAllowed(found);
}

export async function updateCase(id: number, request: ReviewRequest): Promise<Complaint> {
  if (!isDemoMode()) {
    return normalizeComplaint(
      await apiFetch<Complaint>(`/api/complaints/${id}`, { method: "PATCH", body: JSON.stringify(request) })
    );
  }
  return withAllowed(demoReview(id, request));
}

export async function addDiaryEntry(id: number, entry: string): Promise<Complaint> {
  if (!isDemoMode()) {
    return normalizeComplaint(
      await apiFetch<Complaint>(`/api/complaints/${id}/diary`, {
        method: "POST",
        body: JSON.stringify({ entry }),
      })
    );
  }
  if (!entry.trim()) throw new ApiRequestError("Write the diary entry first.", 400);
  return withAllowed(
    demoUpdate(id, (c) => ({
      ...c,
      events: [...(c.events ?? []), demoEvent("diary_entry", entry.trim())],
    }))
  );
}

let demoUnits: string[] | null = null;

export async function fetchUnits(): Promise<string[]> {
  if (!isDemoMode()) {
    return (await apiFetch<{ units: string[] }>("/api/units")).units;
  }
  demoUnits ??= [
    ...new Set([...demoComplaints.map((c) => c.routing.unit), "Cyber Cell", "Local Police Station"]),
  ].sort();
  return demoUnits;
}

// ---------------------------------------------------------------------------
// Citizen portal
// ---------------------------------------------------------------------------

function toCitizenView(c: Complaint): CitizenComplaint {
  const reviewed = !!c.review?.reviewed_at;
  return {
    complaint_id: c.complaint_id,
    complaint_text: c.complaint_text,
    received_at: c.received_at,
    status: c.status ?? "New",
    unit: reviewed ? c.routing.unit : null,
    officer: reviewed ? c.assignment?.officer_name ?? null : null,
    officer_note: c.review?.officer_note ?? null,
    signature_due_at: c.review?.signature_due_at ?? null,
    signature_confirmed_at: c.review?.signature_confirmed_at ?? null,
  };
}

export async function fileCitizenComplaint(complaintText: string): Promise<CitizenComplaint> {
  const trimmed = complaintText.trim();
  if (!isDemoMode()) {
    return normalizeCitizenComplaint(
      await apiFetch<CitizenComplaint>("/api/classify", {
        method: "POST",
        body: JSON.stringify({ complaint_text: trimmed }),
      })
    );
  }
  await wait(700);
  return toCitizenView(demoFile(trimmed, "citizen"));
}

export async function fetchMyComplaints(): Promise<CitizenComplaint[]> {
  if (!isDemoMode()) {
    const data = await apiFetch<{ complaints: CitizenComplaint[] }>("/api/my/complaints?limit=200");
    return data.complaints.map(normalizeCitizenComplaint);
  }
  await wait(300);
  return demoComplaints.filter((c) => c.source === "citizen").map(toCitizenView);
}

// ---------------------------------------------------------------------------
// Staff accounts (administrators)
// ---------------------------------------------------------------------------

export async function fetchStaff(): Promise<StaffAccount[]> {
  if (!isDemoMode()) {
    return (await apiFetch<{ users: StaffAccount[] }>("/api/admin/users")).users;
  }
  return demoStaffWithCounts();
}

export interface StaffChangeResult {
  user: StaffAccount;
  cases_moved?: number;
  cases_assigned?: number;
}

export async function createStaff(account: NewStaffAccount): Promise<StaffChangeResult> {
  if (!isDemoMode()) {
    return apiFetch<StaffChangeResult>("/api/admin/users", { method: "POST", body: JSON.stringify(account) });
  }
  if (demoStaff.some((s) => s.email === account.email.toLowerCase())) {
    throw new ApiRequestError("An account with this email already exists.", 409);
  }
  const created: StaffAccount = {
    id: Math.max(...demoStaff.map((s) => s.id)) + 1,
    email: account.email.toLowerCase(),
    phone: null,
    name: account.name,
    role: account.role,
    unit: account.role === "officer" ? account.unit ?? null : null,
    active: 1,
    open_cases: 0,
    created_at: new Date().toISOString(),
    last_login_at: null,
  };
  demoStaff = [...demoStaff, created];
  return { user: created, cases_assigned: 0 };
}

export async function updateStaff(
  id: number,
  changes: { active?: boolean; unit?: string | null; password?: string }
): Promise<StaffChangeResult> {
  if (!isDemoMode()) {
    return apiFetch<StaffChangeResult>(`/api/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  }
  if (id === DEMO_USERS.admin.id && changes.active === false) {
    throw new ApiRequestError("You cannot deactivate your own account.", 400);
  }
  demoStaff = demoStaff.map((s) =>
    s.id === id
      ? {
          ...s,
          ...(changes.active !== undefined ? { active: changes.active ? 1 : 0 } : {}),
          ...(changes.unit !== undefined ? { unit: changes.unit } : {}),
        }
      : s
  );
  return { user: demoStaffWithCounts().find((s) => s.id === id)!, cases_moved: 0, cases_assigned: 0 };
}

// ---------------------------------------------------------------------------
// Demo mode: an in-memory copy of the backend's case rules
// ---------------------------------------------------------------------------

const TRANSITIONS: Record<ComplaintStatus, ComplaintStatus[]> = {
  New: ["Under Review", "Registered", "Not Registered"],
  "Under Review": ["Registered", "Not Registered"],
  Registered: ["Under Investigation", "Closed"],
  "Under Investigation": ["Charge Sheet Filed", "Closed"],
  "Not Registered": [],
  "Charge Sheet Filed": [],
  Closed: [],
};

const ALL_STATUSES = Object.keys(TRANSITIONS) as ComplaintStatus[];

const EMPTY_REVIEW: ReviewInfo = {
  reviewed_by: null,
  reviewed_at: null,
  officer_note: null,
  original_unit: null,
  override_reason: null,
  signature_confirmed_at: null,
  signature_due_at: null,
};

const DEMO_OFFICER_ASSIGNMENT: Assignment = {
  officer_id: DEMO_USERS.officer.id,
  officer_name: DEMO_USERS.officer.name,
  officer_unit: null,
  assigned_at: new Date().toISOString(),
};

let demoComplaints: Complaint[] = MOCK_COMPLAINTS.map((c) => ({
  ...c,
  status: c.status ?? "New",
  source: "officer",
  review: EMPTY_REVIEW,
  assignment: DEMO_OFFICER_ASSIGNMENT,
  events: [
    { action: "filed", detail: `Filed via officer; routed to ${c.routing.unit}`, created_at: c.received_at, actor: null, actor_role: null },
    { action: "assigned", detail: `Assigned to ${DEMO_USERS.officer.name}`, created_at: c.received_at, actor: null, actor_role: null },
  ],
}));
let simulatedIdCounter = Math.max(...MOCK_COMPLAINTS.map((c) => c.complaint_id)) + 1;

let demoStaff: StaffAccount[] = [DEMO_USERS.admin, DEMO_USERS.officer].map((u) => ({
  ...(u as StaffAccount),
  active: 1,
  open_cases: 0,
  created_at: new Date().toISOString(),
  last_login_at: null,
}));

function demoStaffWithCounts(): StaffAccount[] {
  return demoStaff.map((s) => ({
    ...s,
    open_cases: demoComplaints.filter((c) => c.assignment?.officer_id === s.id && isOpenStatus(c.status)).length,
  }));
}

function demoActor() {
  const role = currentDemoRole() ?? "officer";
  return { name: DEMO_USERS[role].name, role };
}

function demoEvent(action: ComplaintEvent["action"], detail: string | null): ComplaintEvent {
  const actor = demoActor();
  return { action, detail, actor: actor.name, actor_role: actor.role, created_at: new Date().toISOString() };
}

function withAllowed(c: Complaint): Complaint {
  const status = c.status ?? "New";
  const role = currentDemoRole();
  const canAct = role === "admin" || c.assignment?.officer_id === DEMO_USERS.officer.id;
  const allowed = role === "admin" ? ALL_STATUSES.filter((s) => s !== status) : TRANSITIONS[status];
  return { ...c, can_act: canAct, allowed_statuses: canAct ? allowed : [] };
}

function demoUpdate(id: number, change: (c: Complaint) => Complaint): Complaint {
  const c = demoComplaints.find((x) => x.complaint_id === id);
  if (!c) throw new ApiRequestError("Case not found", 404);
  const updated = change(c);
  demoComplaints = demoComplaints.map((x) => (x.complaint_id === id ? updated : x));
  return updated;
}

function demoFile(text: string, source: "citizen" | "officer"): Complaint {
  const now = new Date();
  const filer = source === "citizen" ? DEMO_USERS.citizen : DEMO_USERS.officer;
  const complaint: Complaint = {
    ...classifyLocally(text),
    complaint_id: simulatedIdCounter++,
    received_at: now.toISOString(),
    status: "New",
    source,
    complainant: source === "citizen" ? { name: filer.name, email: filer.email ?? "", phone: filer.phone } : null,
    review: {
      ...EMPTY_REVIEW,
      signature_due_at: source === "citizen" ? new Date(now.getTime() + 3 * 24 * 3600 * 1000).toISOString() : null,
    },
    assignment: { ...DEMO_OFFICER_ASSIGNMENT, assigned_at: now.toISOString() },
  };
  complaint.events = [
    {
      action: "filed",
      detail: `Filed via ${source}; routed to ${complaint.routing.unit}`,
      created_at: now.toISOString(),
      actor: filer.name,
      actor_role: filer.role,
    },
    { action: "assigned", detail: `Assigned to ${DEMO_USERS.officer.name}`, created_at: now.toISOString(), actor: null, actor_role: null },
  ];
  demoComplaints = [complaint, ...demoComplaints];
  return complaint;
}

function demoReview(id: number, req: ReviewRequest): Complaint {
  const c = demoComplaints.find((x) => x.complaint_id === id);
  if (!c) throw new ApiRequestError("Case not found", 404);
  const isAdmin = currentDemoRole() === "admin";
  const current = c.status ?? "New";
  const review: ReviewInfo = { ...(c.review ?? EMPTY_REVIEW) };
  const events = [...(c.events ?? [])];
  const before = events.length;
  let routing = c.routing;
  let assignment = c.assignment;
  let status = req.status;

  if (FINAL_STATUSES.includes(current) && !isAdmin) {
    throw new ApiRequestError("This case is closed. Only an administrator can reopen it.", 400);
  }
  if (status && status !== current && !withAllowed(c).allowed_statuses!.includes(status)) {
    throw new ApiRequestError(`A case that is ${current} cannot move to ${status}.`, 400);
  }
  if (req.unit && req.unit !== routing.unit) {
    if (!req.override_reason) throw new ApiRequestError("Give a reason for transferring the case.", 400);
    review.original_unit ??= routing.unit;
    review.override_reason = req.override_reason;
    events.push(demoEvent("rerouted", `${routing.unit} -> ${req.unit}: ${req.override_reason}`));
    routing = { ...routing, unit: req.unit };
  }
  if (req.assigned_to !== undefined && req.assigned_to !== assignment?.officer_id) {
    const officer = demoStaff.find((s) => s.id === req.assigned_to && s.role === "officer" && s.active);
    if (!officer) throw new ApiRequestError("Choose an active officer.", 400);
    assignment = { officer_id: officer.id, officer_name: officer.name, officer_unit: officer.unit, assigned_at: new Date().toISOString() };
    events.push(demoEvent("assigned", `Assigned to ${officer.name}`));
  }
  if (req.signature_confirmed && c.source === "citizen" && !review.signature_confirmed_at) {
    review.signature_confirmed_at = new Date().toISOString();
    events.push(demoEvent("signature_confirmed", "Informant signature obtained"));
  }
  if (status && NOTE_REQUIRED_STATUSES.includes(status) && !(req.note || review.officer_note)) {
    throw new ApiRequestError("Add a note to the complainant explaining the outcome.", 400);
  }
  if (status === "Registered" && c.source === "citizen" && !review.signature_confirmed_at) {
    throw new ApiRequestError("Confirm the informant has signed the complaint before registering it.", 400);
  }
  const acted = !!req.note || events.slice(before).some((e) => e.action !== "assigned");
  if (!status && current === "New" && acted) status = "Under Review";
  if (status && status !== current) events.push(demoEvent("status_changed", `${current} -> ${status}`));
  if (req.note && req.note !== review.officer_note) {
    review.officer_note = req.note;
    events.push(demoEvent("note_added", req.note));
  }
  if (events.length === before) throw new ApiRequestError("Nothing to update.", 400);

  review.reviewed_by = demoActor().name;
  review.reviewed_at = new Date().toISOString();
  return demoUpdate(id, () => ({ ...c, routing, review, assignment, events, status: status ?? current }));
}


// ---------------------------------------------------------------------------
// Officers: availability and workload
// ---------------------------------------------------------------------------

export interface OfficerWorkload {
  id: number;
  name: string;
  username: string | null;
  unit: string | null;
  station: string | null;
  availability: "available" | "busy" | "on_leave";
  active: boolean;
  open_cases: number;
  weighted_load: number;
  capacity: number;
  load_percent: number;
  last_assigned_at: string | null;
}

export async function fetchOfficers(): Promise<OfficerWorkload[]> {
  if (!isDemoMode()) {
    return (await apiFetch<{ officers: OfficerWorkload[] }>("/api/officers")).officers;
  }
  return demoStaffWithCounts()
    .filter((s) => s.role === "officer")
    .map((s) => ({
      id: s.id,
      name: s.name,
      username: s.username ?? null,
      unit: s.unit,
      station: s.station ?? null,
      availability: "available" as const,
      active: !!s.active,
      open_cases: s.open_cases,
      weighted_load: s.open_cases * 2,
      capacity: 10,
      load_percent: Math.round((s.open_cases / 10) * 100),
      last_assigned_at: null,
    }));
}

export async function setAvailability(availability: OfficerWorkload["availability"]) {
  if (!isDemoMode()) {
    return apiFetch<{ cases_moved: number }>("/api/me/availability", {
      method: "PATCH",
      body: JSON.stringify({ availability }),
    });
  }
  return { cases_moved: 0 };
}

// ---------------------------------------------------------------------------
// Citizens: mobile number and digital signature
// ---------------------------------------------------------------------------

export async function requestNumberChange(phone: string): Promise<string> {
  const res = await apiFetch<{ phone: string }>("/api/auth/phone/change/request", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
  return res.phone;
}

export async function confirmNumberChange(phone: string, code: string) {
  return apiFetch<{ user: { phone: string }; previous_phone: string }>("/api/auth/phone/change/verify", {
    method: "POST",
    body: JSON.stringify({ phone, code }),
  });
}

export async function requestSignatureCode(id: number): Promise<"sms" | "email"> {
  const res = await apiFetch<{ channel: "sms" | "email" }>(`/api/complaints/${id}/sign/request`, { method: "POST" });
  return res.channel;
}

export async function signComplaint(id: number, code: string): Promise<CitizenComplaint> {
  return normalizeCitizenComplaint(
    await apiFetch<CitizenComplaint>(`/api/complaints/${id}/sign`, {
      method: "POST",
      body: JSON.stringify({ code, declaration: true }),
    })
  );
}
