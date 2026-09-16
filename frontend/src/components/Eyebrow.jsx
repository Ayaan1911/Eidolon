// Section kicker. The one accent, two weights:
//   tick — a 2px redact rule + neutral label (quiet, e.g. footer)
//   chip — a solid redact block, parchment label (load-bearing, on sections)
export default function Eyebrow({ children, className = "", variant = "tick" }) {
  if (variant === "chip") {
    return (
      <span
        className={`inline-block bg-redact text-parchment font-mono text-[11px] uppercase tracking-[0.25em] px-2.5 py-1 ${className}`}
      >
        {children}
      </span>
    )
  }
  return (
    <p
      className={`flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.25em] text-parchment-dim ${className}`}
    >
      <span className="inline-block w-8 h-[2px] bg-redact shrink-0" aria-hidden />
      {children}
    </p>
  )
}
