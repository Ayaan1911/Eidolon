import { Link, NavLink } from "react-router-dom"

// Persistent header. Active route is marked with the canonical 2px redact
// rule (the one accent), not an ad-hoc color.
const links = [
  ["/email", "Email"],
  ["/photo", "Photo"],
  ["/repo", "Repo"],
  ["/dossier", "Dossier"],
  ["/trap-lab", "Trap Lab"],
]

const linkClass = ({ isActive }) =>
  `font-mono text-[10px] sm:text-[11px] uppercase tracking-[0.18em] transition-colors pb-0.5 border-b-2 ${
    isActive
      ? "text-parchment border-redact"
      : "text-parchment-dim border-transparent hover:text-parchment"
  }`

export default function Nav() {
  return (
    <nav className="sticky top-0 z-30 border-b border-line/30 bg-void/90 backdrop-blur-sm">
      <div className="max-w-3xl mx-auto flex items-center justify-between px-5 py-3">
        <Link
          to="/"
          className="font-display text-parchment text-base tracking-tight hover:opacity-70 transition-opacity"
        >
          Eidolon
        </Link>
        <ul className="flex items-center gap-4 sm:gap-6">
          {links.map(([to, label]) => (
            <li key={to}>
              <NavLink to={to} className={linkClass}>
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
