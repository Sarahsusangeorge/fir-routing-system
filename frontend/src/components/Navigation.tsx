import { AnimatePresence, motion } from "framer-motion";
import { LogOut, Menu, X } from "lucide-react";
import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import type { Role } from "../types";

const LINKS: Record<Role, { to: string; label: string }[]> = {
  citizen: [
    { to: "/file", label: "File a complaint" },
    { to: "/my-complaints", label: "My complaints" },
  ],
  officer: [
    { to: "/cases", label: "My cases" },
    { to: "/new", label: "New complaint" },
  ],
  admin: [
    { to: "/cases", label: "All cases" },
    { to: "/new", label: "New complaint" },
    { to: "/staff", label: "Staff" },
  ],
};

const ROLE_LABEL: Record<Role, string> = {
  citizen: "Citizen",
  officer: "Officer",
  admin: "Administrator",
};

export default function Navigation() {
  const [open, setOpen] = useState(false);
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const links = user ? LINKS[user.role] : [];
  const who = user ? `${ROLE_LABEL[user.role]}${user.unit ? `, ${user.unit}` : ""}` : "";

  const handleSignOut = async () => {
    setOpen(false);
    await signOut();
    navigate("/login", { replace: true });
  };

  return (
    <header className="fixed top-4 left-0 right-0 z-50 px-4">
      <div className="container-page !px-0">
        <nav className="flex items-center justify-between bg-paper/90 backdrop-blur-md border border-line rounded-[16px] pl-5 pr-2 py-2 md:pl-6 md:pr-3 md:py-2.5 shadow-[0_1px_0_rgba(15,14,18,0.03)]">
          <span className="text-[15px] font-semibold tracking-[0.06em] text-carbon">NIVARA</span>

          <ul className="hidden md:flex items-center gap-1">
            {links.map((link) => (
              <li key={link.to} className="relative">
                <NavLink
                  to={link.to}
                  end={link.to !== "/cases"}
                  className={({ isActive }) =>
                    `relative block px-4 py-2 text-sm rounded-full transition-colors ${
                      isActive ? "text-carbon" : "text-mercury hover:text-carbon"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <motion.span
                          layoutId="nav-pill"
                          className="absolute inset-0 bg-vellum rounded-full"
                          transition={{ type: "spring", stiffness: 380, damping: 32 }}
                        />
                      )}
                      <span className="relative">{link.label}</span>
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>

          {user ? (
            <div className="hidden md:flex items-center gap-3 pl-4">
              <div className="text-right leading-tight">
                <p className="text-sm text-carbon">{user.name}</p>
                <p className="text-xs text-mercury">{who}</p>
              </div>
              <button
                onClick={handleSignOut}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full border border-line text-sm text-carbon hover:bg-vellum transition-colors"
              >
                <LogOut className="w-4 h-4" strokeWidth={1.75} aria-hidden="true" />
                Sign out
              </button>
            </div>
          ) : (
            <span className="hidden md:block pr-3 text-xs text-mercury">Complaint Intelligence &amp; Resolution</span>
          )}

          {user && (
          <button
            className="md:hidden p-3 -mr-1 text-carbon"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <X className="w-5 h-5" strokeWidth={1.5} /> : <Menu className="w-5 h-5" strokeWidth={1.5} />}
          </button>
          )}
        </nav>

        <AnimatePresence>
          {open && user && (
            <motion.div
              initial={{ opacity: 0, y: -8, height: 0 }}
              animate={{ opacity: 1, y: 0, height: "auto" }}
              exit={{ opacity: 0, y: -8, height: 0 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="md:hidden mt-2 bg-paper border border-line rounded-[16px] overflow-hidden"
            >
              <ul className="flex flex-col p-2">
                {links.map((link) => (
                  <li key={link.to}>
                    <NavLink
                      to={link.to}
                      end={link.to !== "/cases"}
                      onClick={() => setOpen(false)}
                      className={({ isActive }) =>
                        `block px-4 py-3 rounded-[10px] text-sm ${
                          isActive ? "bg-vellum text-carbon" : "text-mercury"
                        }`
                      }
                    >
                      {link.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
              <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-line">
                <div className="leading-tight min-w-0">
                  <p className="text-sm text-carbon truncate">{user.name}</p>
                  <p className="text-xs text-mercury truncate">{who}</p>
                </div>
                <button
                  onClick={handleSignOut}
                  className="shrink-0 inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-full border border-line text-sm text-carbon"
                >
                  <LogOut className="w-4 h-4" strokeWidth={1.75} aria-hidden="true" />
                  Sign out
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  );
}
