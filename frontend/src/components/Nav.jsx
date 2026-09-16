import { Link, NavLink } from "react-router-dom"

const links = [
  ["/email", "Email"],
  ["/photo", "Photo"],
  ["/repo", "Repo"],
  ["/dossier", "Dossier"],
  ["/trap-lab", "Trap Lab"],
  ["/system", "System"],
]

// Active route is the single accented (beacon) state in the nav.
const linkClass = ({ isActive }) =>
  `font-mono text-[10px] sm:text-[11px] uppercase tracking-[0.18em] transition-colors ${
    isActive ? "text-beacon" : "text-fg-dim hover:text-fg"
  }`

export default function Nav() {
  return (
    <nav className="sticky top-0 z-30 border-b border-hairline bg-obsidian/90 backdrop-blur-sm">
      <div className="max-w-5xl mx-auto flex items-center justify-between gap-4 px-6 py-3.5">
        <Link to="/" className="font-serif text-lg text-fg hover:text-beacon transition-colors">
          Eidolon
        </Link>
        <ul className="flex items-center gap-3.5 sm:gap-5 flex-wrap justify-end">
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
