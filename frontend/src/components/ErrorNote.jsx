import Stamp from "./Stamp"

// Errors carry the canonical accent as a stamp (not ad-hoc red text).
// Sits on paper surfaces, so the message uses ink-soft.
export default function ErrorNote({ children, className = "" }) {
  return (
    <p className={`flex items-center gap-2 text-sm mt-3 ${className}`}>
      <Stamp label="Error" tone="critical" />
      <span className="text-ink-soft">{children}</span>
    </p>
  )
}
