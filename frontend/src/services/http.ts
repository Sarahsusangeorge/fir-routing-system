/**
 * Shared HTTP client for the NIVARA API.
 *
 * Sessions live in an httpOnly cookie that page scripts cannot read, so every
 * request is sent with credentials. State-changing requests also carry the
 * CSRF token in an X-CSRF-TOKEN header; the backend compares it with the
 * token inside the session. The CSRF token is kept in memory and refreshed
 * whenever the backend sends a new one.
 */

export const API_BASE_URL = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "").replace(/\/+$/, "");

/** True when no backend is configured: the app runs on local demo data. */
export function isDemoMode(): boolean {
  return !API_BASE_URL;
}

/** Raised when the session is missing or expired. The app returns to sign-in. */
export class AuthError extends Error {}

/** Raised when the backend answers with an error message. */
export class ApiRequestError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Raised when the backend cannot be reached at all. */
export class NetworkError extends Error {}

export const UNAUTHORIZED_EVENT = "nivara:unauthorized";

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null | undefined) {
  csrfToken = token ?? null;
}

function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrf_access_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (method !== "GET" && method !== "HEAD") {
    const token = csrfToken ?? readCsrfCookie();
    if (token) headers.set("X-CSRF-TOKEN", token);
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, method, headers, credentials: "include" });
  } catch {
    throw new NetworkError("The NIVARA service could not be reached.");
  }

  const refreshed = res.headers.get("X-CSRF-TOKEN");
  if (refreshed) csrfToken = refreshed;

  const body = (await res.json().catch(() => null)) as { error?: string; code?: string } | null;

  if (res.status === 401 && body?.code === "AUTH_REQUIRED") {
    csrfToken = null;
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
    throw new AuthError(body.error ?? "Please sign in to continue.");
  }
  if (!res.ok) {
    throw new ApiRequestError(body?.error ?? "The request could not be completed.", res.status, body?.code);
  }
  return body as T;
}
