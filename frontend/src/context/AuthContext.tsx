import { useCallback, useEffect, useMemo, useState } from "react";
import * as auth from "../services/auth";
import { UNAUTHORIZED_EVENT } from "../services/http";
import type { User } from "../types";
import { AuthContext, type AuthState } from "./useAuth";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    let cancelled = false;
    auth.fetchCurrentUser().then((u) => {
      if (!cancelled) {
        setUser(u);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Any request that comes back "not signed in" ends the session here, which
  // sends the user to the sign-in page with an explanation.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser((current) => {
        if (current) setSessionExpired(true);
        return null;
      });
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const signedIn = useCallback((u: User) => {
    setSessionExpired(false);
    setUser(u);
    return u;
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      sessionExpired,
      staffSignIn: async (email, password) => signedIn(await auth.staffSignIn(email, password)),
      requestCode: auth.requestSignInCode,
      verifyCode: async (channel, identifier, code, name, contact) =>
        signedIn(await auth.verifySignInCode(channel, identifier, code, name, contact)),
      demoSignIn: (role) => signedIn(auth.demoSignIn(role)),
      signOut: async () => {
        await auth.signOut().catch(() => undefined);
        setSessionExpired(false);
        setUser(null);
      },
    }),
    [user, loading, sessionExpired, signedIn]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
