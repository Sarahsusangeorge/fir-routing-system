export default function Footer() {
  return (
    <footer className="bg-onyx text-vellum mt-32">
      <div className="container-page py-16 flex flex-col md:flex-row md:items-end justify-between gap-10">
        <div>
          <span className="text-[15px] font-semibold tracking-[0.06em]">NIVARA</span>
          <p className="text-sm text-vellum/50 mt-2 max-w-xs">Complaint Intelligence &amp; Resolution Platform</p>
        </div>
        <p className="text-sm text-vellum/60 max-w-md leading-[1.6]">
          NIVARA is a decision-support and triage system. AI assists, a human reviews, and the officer decides —
          NIVARA does not determine guilt, innocence, or final legal outcomes.
        </p>
      </div>
      <div className="container-page py-5 border-t border-vellum/10 text-xs text-vellum/40">
        Academic research prototype.
      </div>
    </footer>
  );
}
