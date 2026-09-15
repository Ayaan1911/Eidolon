import { Link } from "react-router-dom"
import { useMagnetic } from "../lib/motion"

// Canonical call-to-action. Neutral by rule — red is reserved for the stamp
// and the accent rule, never a button. variant: "outline" | "solid".
export default function Cta({ to, variant = "outline", className = "", children }) {
  const ref = useMagnetic(0.25)
  const style =
    variant === "solid"
      ? "bg-parchment text-void hover:bg-parchment/90"
      : "border border-parchment-dim/40 text-parchment hover:border-parchment hover:bg-parchment/5"
  return (
    <Link
      ref={ref}
      to={to}
      className={`inline-block font-mono text-xs uppercase tracking-[0.15em] px-4 py-2 transition duration-150 ease-out will-change-transform ${style} ${className}`}
    >
      {children}
    </Link>
  )
}
