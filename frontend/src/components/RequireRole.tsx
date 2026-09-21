import { Loader2 } from "lucide-react";
import { Navigate, useLocation } from "react-router-dom";
import { homePathFor, useAuth } from "../context/useAuth";
import type { Role } from "../types";

export function PageLoader() {
  return (
    <div className="container-page pt-40 pb-24 flex justify-center" role="status" aria-live="polite">
      <Loader2 className="w-5 h-5 animate-spin text-mercury" strokeWidth={1.75} />
      <span className="sr-only">Loading</span>
    </div>
  );
}

interface RequireRoleProps {
  roles: Role[];
  children: React.ReactNode;
}

/**
 * Shows children only to a signed-in user with one of the given roles.
 * This keeps people out of screens they cannot use; the backend enforces
 * the same rules on every request, which is what actually protects the data.
 */
export default function RequireRole({ roles, children }: RequireRoleProps) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!roles.includes(user.role)) return <Navigate to={homePathFor(user.role)} replace />;
  return <>{children}</>;
}
