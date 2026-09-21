export type PriorityLevel = "High" | "Medium" | "Low";

export interface Section {
  code: string;
  title: string;
  confidence: number; // 0–1
}

export interface Priority {
  level: PriorityLevel;
  score: number; // 0–10
  /** Section code that set the score, when the backend reports one. */
  driver?: string;
  /** Human-readable one-line justification, e.g. "Driven by Section 392: severity 8 x confidence 0.87 = 7". */
  basis?: string;
}

export interface Routing {
  unit: string;
  reason: string;
  /** Section code that determined routing, when the backend reports one. */
  matched_section?: string;
}

export interface ExplanationToken {
  token: string;
  weight: number; // 0–1
}

export type ComplaintStatus =
  | "New"
  | "Under Review"
  | "Registered"
  | "Not Registered"
  | "Under Investigation"
  | "Charge Sheet Filed"
  | "Closed";

export const FINAL_STATUSES: ComplaintStatus[] = ["Not Registered", "Charge Sheet Filed", "Closed"];

/** Statuses that need a note to the complainant. */
export const NOTE_REQUIRED_STATUSES: ComplaintStatus[] = ["Not Registered", "Closed"];

export function isOpenStatus(status: ComplaintStatus | undefined): boolean {
  return !FINAL_STATUSES.includes(status ?? "New");
}

export interface Assignment {
  officer_id: number | null;
  officer_name: string | null;
  officer_unit: string | null;
  officer_station?: string | null;
  assigned_at: string | null;
}

export interface ReviewInfo {
  reviewed_by: string | null;
  reviewed_at: string | null;
  /** Shown to the complainant. */
  officer_note: string | null;
  /** Set only when an officer changed the routed unit. */
  original_unit: string | null;
  override_reason: string | null;
  signature_confirmed_at: string | null;
  signature_method?: "digital" | "in_person" | null;
  signature_evidence?: string | null;
  /** Citizen-filed complaints only: three days after receipt (BNSS s.173). */
  signature_due_at: string | null;
}

export interface ComplaintEvent {
  action:
    | "filed"
    | "assigned"
    | "status_changed"
    | "rerouted"
    | "signature_confirmed"
    | "note_added"
    | "diary_entry";
  detail: string | null;
  created_at: string;
  actor: string | null;
  actor_role: Role | null;
}

export interface Complaint {
  complaint_id: number;
  complaint_text: string;
  received_at: string; // ISO timestamp
  sections: Section[];
  priority: Priority;
  routing: Routing;
  explanation: ExplanationToken[];
  /** Present on records from the authenticated API; absent on older mock data. */
  status?: ComplaintStatus;
  source?: "citizen" | "officer";
  complainant?: { name: string; email: string; phone: string | null } | null;
  review?: ReviewInfo;
  assignment?: Assignment;
  events?: ComplaintEvent[];
  /** Statuses the signed-in user may move this case to. */
  allowed_statuses?: ComplaintStatus[];
  /** False when an officer may read the case but not act on it. */
  can_act?: boolean;
  station?: string | null;
}

/** What a complainant sees about their own complaint. */
export interface CitizenComplaint {
  complaint_id: number;
  complaint_text: string;
  received_at: string;
  status: ComplaintStatus;
  /** Null until an officer has reviewed the complaint. */
  unit: string | null;
  /** Investigating officer, once the complaint has been reviewed. */
  officer: string | null;
  officer_note: string | null;
  officer_unit?: string | null;
  officer_station?: string | null;
  station?: string | null;
  signature_due_at: string | null;
  signature_confirmed_at: string | null;
  signature_method?: "digital" | "in_person" | null;
  /** True while the complainant may still sign online. */
  can_sign_digitally?: boolean;
  events?: { action: string; detail: string | null; created_at: string }[];
}

export interface ReviewRequest {
  status?: ComplaintStatus;
  unit?: string;
  override_reason?: string;
  note?: string;
  signature_confirmed?: boolean;
  /** Administrators only. */
  assigned_to?: number;
}

export type Role = "citizen" | "officer" | "admin";

export type SignInChannel = "email" | "sms";

export interface User {
  id: number;
  username?: string | null;
  /** Staff always have one; citizens have an email, a mobile number or both. */
  email: string | null;
  phone: string | null;
  name: string;
  role: Role;
  /** Officers: the unit whose queue they work. Null means every unit. */
  unit: string | null;
}

export interface StaffAccount extends User {
  role: "officer" | "admin";
  email: string;
  station?: string | null;
  active: number;
  open_cases: number;
  created_at: string;
  last_login_at: string | null;
}

export interface NewStaffAccount {
  email: string;
  name: string;
  role: "officer" | "admin";
  password: string;
  unit?: string | null;
}

export interface ClassifyRequest {
  complaint_text: string;
}

export type ClassifyResponse = Complaint;

export interface ApiError {
  error: string;
}

export interface ComplaintsListResponse {
  complaints: Complaint[];
}

export interface ScanResult {
  extracted_text: string;
  /** OCR engine confidence, 0–100. Undefined when the source doesn't report one. */
  confidence?: number;
}
