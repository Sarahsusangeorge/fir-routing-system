import { motion } from "framer-motion";
import { ArrowLeft, Info, Loader2 } from "lucide-react";
import { useId, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import SectionLabel from "../components/SectionLabel";
import { homePathFor, useAuth } from "../context/useAuth";
import { ApiRequestError, isDemoMode } from "../services/http";
import type { Role, SignInChannel, User } from "../types";
import { formatPhone } from "../utils/format";

type Audience = "citizen" | "staff";

const inputClass =
  "w-full rounded-[10px] border border-line bg-vellum/40 px-4 py-3 text-[16px] text-carbon placeholder:text-mercury focus:outline-none focus:ring-2 focus:ring-carbon/30 focus:border-carbon/40 disabled:opacity-60";

const primaryButton =
  "w-full inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-full bg-carbon text-vellum text-[15px] font-medium hover:bg-onyx active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed";

const ALLOWED_PATHS: Record<Role, RegExp> = {
  citizen: /^\/(file|my-complaints)$/,
  officer: /^\/(cases(\/\d+)?|new)$/,
  admin: /^\/(cases(\/\d+)?|new|staff)$/,
};

function errorText(err: unknown) {
  return err instanceof Error ? err.message : "Something went wrong. Try again.";
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: (id: string, describedBy?: string) => React.ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-carbon mb-2">
        {label}
      </label>
      {children(id, hint ? hintId : undefined)}
      {hint && (
        <p id={hintId} className="text-xs text-mercury mt-2">
          {hint}
        </p>
      )}
    </div>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-sm text-[color:var(--color-priority-high)]">
      {message}
    </p>
  );
}

const CHANNELS: { value: SignInChannel; label: string }[] = [
  { value: "sms", label: "Mobile number" },
  { value: "email", label: "Email" },
];

function CitizenSignIn({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const { requestCode, verifyCode } = useAuth();
  const [channel, setChannel] = useState<SignInChannel>("sms");
  const [step, setStep] = useState<"address" | "code">("address");
  const [address, setAddress] = useState("");
  const [sentTo, setSentTo] = useState("");
  const [code, setCode] = useState("");
  const [needsName, setNeedsName] = useState(false);
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const isSms = channel === "sms";
  const shown = isSms ? formatPhone(sentTo) : sentTo;

  const sendCode = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const identifier = await requestCode(channel, address.trim());
      setSentTo(identifier);
      setStep("code");
      setNotice(`We sent a 6-digit code to ${isSms ? formatPhone(identifier) : identifier}. It expires in 10 minutes.`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const submitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onSignedIn(
        await verifyCode(channel, sentTo, code.trim(), needsName ? name.trim() : undefined, contact.trim() || undefined)
      );
    } catch (err) {
      if (err instanceof ApiRequestError && err.code === "NAME_REQUIRED") {
        // The code was correct; the account just needs a name first.
        setError(needsName ? err.message : null);
        setNeedsName(true);
        setNotice("Your code is correct. As this is your first complaint, tell us who you are.");
      } else {
        setError(errorText(err));
      }
    } finally {
      setBusy(false);
    }
  };

  if (step === "address") {
    return (
      <form onSubmit={sendCode} className="flex flex-col gap-5" noValidate>
        <div role="radiogroup" aria-label="Sign in with" className="flex gap-2">
          {CHANNELS.map((c) => (
            <button
              key={c.value}
              type="button"
              role="radio"
              aria-checked={channel === c.value}
              onClick={() => {
                setChannel(c.value);
                setAddress("");
                setError(null);
              }}
              className={`px-4 py-2 rounded-full text-sm border transition-colors ${
                channel === c.value
                  ? "border-carbon bg-carbon text-vellum"
                  : "border-line text-mercury hover:text-carbon hover:border-carbon/40"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {isSms ? (
          <Field label="Mobile number" hint="We'll text you a one-time code. Indian mobile numbers only.">
            {(id, describedBy) => (
              <div className="flex rounded-[10px] border border-line bg-vellum/40 focus-within:ring-2 focus-within:ring-carbon/30 focus-within:border-carbon/40">
                <span className="pl-4 pr-2 py-3 text-[16px] text-mercury select-none" aria-hidden="true">
                  +91
                </span>
                <input
                  id={id}
                  aria-describedby={describedBy}
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel-national"
                  required
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="flex-1 min-w-0 bg-transparent pr-4 py-3 text-[16px] text-carbon placeholder:text-mercury focus:outline-none"
                  placeholder="98765 43210"
                />
              </div>
            )}
          </Field>
        ) : (
          <Field label="Email address" hint="We'll email you a one-time code. No password needed.">
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                type="email"
                autoComplete="email"
                inputMode="email"
                required
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className={inputClass}
                placeholder="you@example.com"
              />
            )}
          </Field>
        )}
        <FormError message={error} />
        <button type="submit" className={primaryButton} disabled={busy || !address.trim()}>
          {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
          Send code
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={submitCode} className="flex flex-col gap-5" noValidate>
      {notice && <p className="text-sm text-mercury">{notice}</p>}
      <Field label="Sign-in code">
        {(id, describedBy) => (
          <input
            id={id}
            aria-describedby={describedBy}
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className={`${inputClass} tracking-[0.4em] tabular-nums`}
            placeholder="000000"
          />
        )}
      </Field>

      {needsName && (
        <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-5">
          <Field label="Full name" hint="As it should appear on your complaint.">
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                autoComplete="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputClass}
              />
            )}
          </Field>
          <Field
            label={isSms ? "Email address (optional)" : "Mobile number (optional)"}
            hint="Another way for the police to reach you about your complaint."
          >
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                type={isSms ? "email" : "tel"}
                autoComplete={isSms ? "email" : "tel"}
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                className={inputClass}
              />
            )}
          </Field>
        </motion.div>
      )}

      <FormError message={error} />
      <button
        type="submit"
        className={primaryButton}
        disabled={busy || code.length !== 6 || (needsName && name.trim().length < 2)}
      >
        {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
        {needsName ? "Create account and continue" : "Sign in"}
      </button>
      <div className="flex items-center justify-between gap-3 text-sm">
        <button
          type="button"
          onClick={() => {
            setStep("address");
            setCode("");
            setNeedsName(false);
            setError(null);
          }}
          className="inline-flex items-center gap-1.5 text-mercury hover:text-carbon py-2 text-left"
        >
          <ArrowLeft className="w-4 h-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          {isSms ? "Change number" : "Change email"}
        </button>
        <button
          type="button"
          onClick={() => sendCode()}
          disabled={busy}
          aria-label={`Send a new code to ${shown}`}
          className="text-mercury hover:text-carbon underline underline-offset-4 py-2 disabled:opacity-40"
        >
          Send a new code
        </button>
      </div>
    </form>
  );
}

function StaffSignIn({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const { staffSignIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onSignedIn(await staffSignIn(email.trim(), password));
    } catch (err) {
      setError(errorText(err));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <Field label="Username or official email">
        {(id, describedBy) => (
          <input
            id={id}
            aria-describedby={describedBy}
            type="text"
            autoCapitalize="none"
            spellCheck={false}
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        )}
      </Field>
      <Field label="Password" hint="Staff accounts are issued by your administrator.">
        {(id, describedBy) => (
          <input
            id={id}
            aria-describedby={describedBy}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        )}
      </Field>
      <FormError message={error} />
      <button type="submit" className={primaryButton} disabled={busy || !email.trim() || !password}>
        {busy && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
        Sign in
      </button>
    </form>
  );
}

function DemoSignIn({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const { demoSignIn } = useAuth();
  const options: { role: Role; label: string; detail: string }[] = [
    { role: "citizen", label: "Continue as a citizen", detail: "File a complaint and track its status" },
    { role: "officer", label: "Continue as an officer", detail: "Work the cases allocated to you" },
    { role: "admin", label: "Continue as an administrator", detail: "See every case, reassign cases and manage staff" },
  ];
  return (
    <div className="flex flex-col gap-3">
      <p className="flex items-start gap-2 text-xs text-mercury mb-2">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        Demo mode: no backend is configured, so there is nothing to sign in to. Pick a role to explore that view
        with synthetic data.
      </p>
      {options.map((o) => (
        <button
          key={o.role}
          onClick={() => onSignedIn(demoSignIn(o.role))}
          className="text-left px-5 py-4 rounded-[16px] border border-line hover:border-carbon/40 hover:bg-vellum/50 transition-colors"
        >
          <span className="block text-[15px] font-medium text-carbon">{o.label}</span>
          <span className="block text-sm text-mercury mt-0.5">{o.detail}</span>
        </button>
      ))}
    </div>
  );
}

export default function LoginPage() {
  const { user, loading, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [audience, setAudience] = useState<Audience>("citizen");

  const from = (location.state as { from?: string } | null)?.from;

  const onSignedIn = (u: User) => {
    navigate(from && ALLOWED_PATHS[u.role].test(from) ? from : homePathFor(u.role), { replace: true });
  };

  if (!loading && user) return <Navigate to={homePathFor(user.role)} replace />;

  return (
    <div className="container-page pt-32 pb-24">
      <div className="grid lg:grid-cols-[1fr_440px] gap-10 lg:gap-20 items-start">
        <div className="lg:pt-6">
          <SectionLabel className="mb-6">Sign in</SectionLabel>
          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="text-[32px] md:text-[52px] font-light leading-[1.05] tracking-[0.01em] text-carbon max-w-xl"
          >
            Report a crime, or work the complaint queue.
          </motion.h1>
          <p className="hidden sm:block text-base text-mercury mt-6 max-w-md leading-[1.55]">
            Citizens sign in with a code sent to their mobile number or email to file a complaint and follow its
            progress. Police staff sign in to work the cases allocated to them.
          </p>
          <p className="text-sm text-mercury mt-4 sm:mt-6 max-w-md leading-[1.55]">
            In an emergency, call 112. Online complaints are reviewed by an officer and are not a substitute for
            urgent help.
          </p>
          <p role="note" className="text-sm text-carbon mt-4 max-w-md leading-[1.55] border-l-2 border-carbon pl-3">
            NIVARA is a student research prototype, not an official police service. Do not report real incidents
            here.
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="bg-paper border border-line rounded-[24px] p-6 md:p-8"
        >
          {sessionExpired && (
            <p role="status" className="text-sm text-carbon bg-vellum rounded-[10px] px-4 py-3 mb-6">
              Your session ended. Sign in again to continue.
            </p>
          )}

          {isDemoMode() ? (
            <DemoSignIn onSignedIn={onSignedIn} />
          ) : (
            <>
              <div role="tablist" aria-label="Who is signing in" className="grid grid-cols-2 p-1 rounded-full bg-vellum mb-8">
                {(["citizen", "staff"] as Audience[]).map((a) => (
                  <button
                    key={a}
                    id={`signin-tab-${a}`}
                    role="tab"
                    aria-selected={audience === a}
                    aria-controls="signin-panel"
                    tabIndex={audience === a ? 0 : -1}
                    onClick={() => setAudience(a)}
                    onKeyDown={(e) => {
                      // WAI-ARIA tabs: arrow keys move between tabs.
                      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
                      e.preventDefault();
                      const next: Audience = audience === "citizen" ? "staff" : "citizen";
                      setAudience(next);
                      document.getElementById(`signin-tab-${next}`)?.focus();
                    }}
                    className={`relative py-2.5 rounded-full text-sm transition-colors ${
                      audience === a ? "text-carbon" : "text-mercury hover:text-carbon"
                    }`}
                  >
                    {audience === a && (
                      <motion.span
                        layoutId="audience-pill"
                        className="absolute inset-0 bg-paper rounded-full shadow-[0_1px_2px_rgba(15,14,18,0.06)]"
                        transition={{ type: "spring", stiffness: 380, damping: 32 }}
                      />
                    )}
                    <span className="relative">{a === "citizen" ? "Citizen" : "Police staff"}</span>
                  </button>
                ))}
              </div>
              <div role="tabpanel" id="signin-panel" aria-labelledby={`signin-tab-${audience}`}>
                {audience === "citizen" ? (
                  <CitizenSignIn onSignedIn={onSignedIn} />
                ) : (
                  <StaffSignIn onSignedIn={onSignedIn} />
                )}
              </div>
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
}
