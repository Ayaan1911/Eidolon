import { Link } from "react-router-dom"
import { useMagnetic } from "../lib/motion"

// Canonical call-to-action.
//   outline — secondary (neutral, on dark)
//   solid   — lit paper fill (primary on a red surface)
//   danger  — the load-bearing red block (primary action)
const styles = {
  outline: "border border-parchment-dim/40 text-parchment hover:border-parchment hover:bg-parchment/5",
  solid: "bg-parchment text-void hover:bg-parchment/90",
  danger: "bg-redact text-parchment hover:bg-redact/90",
}

export default function Cta({ to, variant = "outline", className = "", children }) {
  const ref = useMagnetic(0.25)
  return (
    <Link
      ref={ref}
      to={to}
      className={`inline-block font-mono text-xs uppercase tracking-[0.15em] px-4 py-2 transition duration-150 ease-out will-change-transform ${
        styles[variant] || styles.outline
      } ${className}`}
    >
      {children}
    </Link>
  )
}
