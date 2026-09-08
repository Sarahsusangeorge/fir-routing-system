import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/", label: "Analyze" },
  { to: "/history", label: "History" },
];

export default function Navigation() {
  const [open, setOpen] = useState(false);

  return (
    <header className="fixed top-4 left-0 right-0 z-50 px-4">
      <div className="container-page !px-0">
        <nav className="flex items-center justify-between bg-paper/90 backdrop-blur-md border border-line rounded-[16px] pl-5 pr-2 py-2 md:pl-6 md:pr-3 md:py-2.5 shadow-[0_1px_0_rgba(15,14,18,0.03)]">
          <span className="text-[15px] font-semibold tracking-[0.06em] text-carbon">NIVARA</span>

          <ul className="hidden md:flex items-center gap-1">
            {LINKS.map((link) => (
              <li key={link.to} className="relative">
                <NavLink
                  to={link.to}
                  end={link.to === "/"}
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

          <div className="hidden md:flex items-center gap-2 pl-4 pr-2 text-xs text-mercury">
            <span className="relative flex w-1.5 h-1.5">
              <span className="absolute inline-flex h-full w-full rounded-full bg-[color:var(--color-priority-low)] opacity-60 animate-ping" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[color:var(--color-priority-low)]" />
            </span>
            System operational
          </div>

          <button
            className="md:hidden p-3 -mr-1 text-carbon"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <X className="w-5 h-5" strokeWidth={1.5} /> : <Menu className="w-5 h-5" strokeWidth={1.5} />}
          </button>
        </nav>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: -8, height: 0 }}
              animate={{ opacity: 1, y: 0, height: "auto" }}
              exit={{ opacity: 0, y: -8, height: 0 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="md:hidden mt-2 bg-paper border border-line rounded-[16px] overflow-hidden"
            >
              <ul className="flex flex-col p-2">
                {LINKS.map((link) => (
                  <li key={link.to}>
                    <NavLink
                      to={link.to}
                      end={link.to === "/"}
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
              <div className="flex items-center gap-2 px-4 py-3 border-t border-line text-xs text-mercury">
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[color:var(--color-priority-low)]" />
                System operational
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  );
}
