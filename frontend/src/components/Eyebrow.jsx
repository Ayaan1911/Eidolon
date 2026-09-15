// Section kicker: the canonical 2px redact rule (the one accent) + a neutral
// mono label. Used sitewide so the accent reads as one signature.
export default function Eyebrow({ children, className = "" }) {
  return (
    <p
      className={`flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.25em] text-parchment-dim ${className}`}
    >
      <span className="inline-block w-8 h-[2px] bg-redact shrink-0" aria-hidden />
      {children}
    </p>
  )
}
