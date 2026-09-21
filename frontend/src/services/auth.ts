import type { Role, SignInChannel, User } from "../types";
import { apiFetch, isDemoMode, setCsrfToken } from "./http";

interface SessionResponse {
  user: User;
  csrf_token: string | null;
}

/** Demo mode has no backend, so sign-in is a role picker. */
export const DEMO_USERS: Record<Role, User> = {
  citizen: { id: 9001, email: "citizen@nivara.test", phone: null, name: "Demo Citizen", role: "citizen", unit: null },
  officer: { id: 9002, email: "duty.officer@nivara.test", phone: null, name: "SI Kavya Nair", role: "officer", unit: null },
  admin: { id: 9003, email: "admin@nivara.test", phone: null, name: "Demo Administrator", role: "admin", unit: null },
};

const DEMO_SESSION_KEY = "nivara-demo-role";

/** The role picked on the demo sign-in screen, if any. */
export function currentDemoRole(): Role | null {
  return readDemoRole();
}

function readDemoRole(): Role | null {
  try {
    const role = sessionStorage.getItem(DEMO_SESSION_KEY);
    return role && role in DEMO_USERS ? (role as Role) : null;
  } catch {
    return null;
  }
}

export function demoSignIn(role: Role): User {
  try {
    sessionStorage.setItem(DEMO_SESSION_KEY, role);
  } catch {
    // Private browsing can block storage; the session then lasts until reload.
  }
  return DEMO_USERS[role];
}

function accept(session: SessionResponse): User {
  setCsrfToken(session.csrf_token);
  return session.user;
}

/** The signed-in user, or null. */
export async function fetchCurrentUser(): Promise<User | null> {
  if (isDemoMode()) {
    const role = readDemoRole();
    return role ? DEMO_USERS[role] : null;
  }
  try {
    return accept(await apiFetch<SessionResponse>("/api/auth/me"));
  } catch {
    return null;
  }
}

export async function staffSignIn(email: string, password: string): Promise<User> {
  return accept(
    await apiFetch<SessionResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
  );
}

/** Sends a code and returns the address in the form the backend uses. */
export async function requestSignInCode(channel: SignInChannel, identifier: string): Promise<string> {
  const res = await apiFetch<{ identifier: string }>("/api/auth/otp/request", {
    method: "POST",
    body: JSON.stringify({ channel, identifier }),
  });
  return res.identifier;
}

/**
 * contact: optional second way to reach a new citizen (a mobile number when
 * signing in by email, or an email when signing in by mobile).
 */
export async function verifySignInCode(
  channel: SignInChannel,
  identifier: string,
  code: string,
  name?: string,
  contact?: string
): Promise<User> {
  return accept(
    await apiFetch<SessionResponse>("/api/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ channel, identifier, code, name, contact }),
    })
  );
}

export async function signOut(): Promise<void> {
  if (isDemoMode()) {
    try {
      sessionStorage.removeItem(DEMO_SESSION_KEY);
    } catch {
      // nothing to clear
    }
    return;
  }
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } finally {
    setCsrfToken(null);
  }
}
