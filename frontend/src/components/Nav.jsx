import { Link, NavLink } from "react-router-dom"

// Persistent header. Real route links now (was anchor-scroll); the active
// route lights up with the redact underline.
const links = [
  ["/email", "Email"],
  ["/photo", "Photo"],
  ["/repo", "Repo"],
  ["/dossier", "Dossier"],
  ["/trap-lab", "Trap Lab"],
]

const linkClass = ({ isActive }) =>
  `font-mono text-[10px] sm:text-[11px] uppercase tracking-[0.18em] transition-colors ${
    isActive
      ? "text-parchment underline decoration-redact underline-offset-4"
      : "text-parchment-dim hover:text-parchment"
  }`

export default function Nav() {
  return (
    <nav className="sticky top-0 z-30 border-b border-line/30 bg-void/90 backdrop-blur-sm">
      <div className="max-w-2xl mx-auto flex items-center justify-between px-4 py-3">
        <Link
          to="/"
          className="font-display text-parchment text-base tracking-tight hover:text-redact transition-colors"
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
