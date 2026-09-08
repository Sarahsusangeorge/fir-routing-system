import type { ApiError, Complaint } from "../types";
import { classifyLocally } from "./localClassifier";
import { MOCK_COMPLAINTS } from "./mockData";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined;

export class ClassificationError extends Error {}

/** In-memory session store so newly analyzed complaints appear in History
 *  immediately, without a backend. Seeded from the mock dataset. */
let sessionComplaints: Complaint[] = [...MOCK_COMPLAINTS];
let simulatedIdCounter = Math.max(...MOCK_COMPLAINTS.map((c) => c.complaint_id)) + 1;

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Adapts a raw backend response into the shape the UI relies on, without
 * requiring any change to the backend's own contract:
 *  - `complaint_text` isn't echoed back by POST /api/classify, so it's
 *    filled in from the text we just sent.
 *  - `explanation` isn't persisted for historical complaints returned by
 *    GET /api/complaints, so it defaults to an empty array rather than
 *    being undefined.
 *  - `received_at` comes back as "YYYY-MM-DD HH:MM:SS" (SQLite's
 *    datetime('now')), which most browsers parse fine but isn't strictly
 *    ISO 8601 — normalized here so `new Date(...)` is reliable everywhere.
 */
function normalizeComplaint(raw: Complaint, fallbackText?: string): Complaint {
  return {
    ...raw,
    complaint_text: raw.complaint_text || fallbackText || "",
    explanation: raw.explanation ?? [],
    received_at: /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(raw.received_at)
      ? raw.received_at.replace(" ", "T")
      : raw.received_at,
  };
}

/**
 * Whether the app is operating against the real backend or the local
 * demo dataset. Exposed so the UI can (optionally) surface demo-mode
 * status without pretending to be connected to a live service.
 */
export function isDemoMode(): boolean {
  return !API_BASE_URL;
}

export async function classifyComplaint(complaintText: string): Promise<Complaint> {
  const trimmed = complaintText.trim();
  if (!trimmed) {
    throw new ClassificationError("Complaint text is required");
  }

  if (API_BASE_URL) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ complaint_text: trimmed }),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as ApiError | null;
        throw new ClassificationError(body?.error ?? "The classification service could not be reached.");
      }

      const data = normalizeComplaint((await res.json()) as Complaint, trimmed);
      sessionComplaints = [data, ...sessionComplaints];
      return data;
    } catch (err) {
      if (err instanceof ClassificationError) throw err;
      // Network failure — fall through to local demo classifier below.
    }
  }

  // Demo mode: simulate latency and classify locally.
  await wait(600 + Math.random() * 400);
  const result = classifyLocally(trimmed);
  result.complaint_id = simulatedIdCounter++;
  sessionComplaints = [result, ...sessionComplaints];
  return result;
}

export async function fetchComplaints(): Promise<Complaint[]> {
  if (API_BASE_URL) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/complaints`);
      if (res.ok) {
        const data = (await res.json()) as Complaint[] | { complaints: Complaint[] };
        const list = Array.isArray(data) ? data : data.complaints;
        return list.map((c) => normalizeComplaint(c));
      }
    } catch {
      // fall through to demo data
    }
  }

  await wait(450);
  return sessionComplaints;
}
