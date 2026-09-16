import { Link } from "react-router-dom"
import { useMagnetic } from "../lib/motion"

// Pill CTAs. fill = the one accent (primary action); ghost = hairline
// (secondary). Nothing else carries color.
const variants = {
  fill: "bg-beacon text-on-beacon border border-beacon hover:bg-beacon/90",
  ghost: "text-fg border border-hairline hover:border-edge",
}

export default function Cta({ to, variant = "ghost", className = "", children }) {
  const ref = useMagnetic(0.2)
  return (
    <Link
      ref={ref}
      to={to}
      className={`inline-flex items-center gap-2 rounded-full font-sans text-sm px-5 py-2.5 transition duration-150 ease-out will-change-transform ${
        variants[variant] || variants.ghost
      } ${className}`}
    >
      {children}
    </Link>
  )
}
