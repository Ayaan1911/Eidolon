// Section eyebrow: tracked-out mono caps, quiet. No accent, no rule.
export default function Eyebrow({ children, className = "" }) {
  return (
    <p className={`font-mono text-[11px] uppercase tracking-[0.3em] text-fg-faint ${className}`}>
      {children}
    </p>
  )
}
