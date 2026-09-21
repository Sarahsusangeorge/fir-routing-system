import { createContext, useContext } from "react";
import type { Role, SignInChannel, User } from "../types";

export interface AuthState {
  user: User | null;
  /** True until the initial session check has finished. */
  loading: boolean;
  /** Set when the session ended on its own, so the sign-in page can say why. */
  sessionExpired: boolean;
  staffSignIn: (email: string, password: string) => Promise<User>;
  requestCode: (channel: SignInChannel, identifier: string) => Promise<string>;
  verifyCode: (
    channel: SignInChannel,
    identifier: string,
    code: string,
    name?: string,
    contact?: string
  ) => Promise<User>;
  demoSignIn: (role: Role) => User;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Where each role lands after signing in. */
export function homePathFor(role: Role): string {
  return role === "citizen" ? "/file" : "/cases";
}
