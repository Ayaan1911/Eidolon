// Persistent header. Anchor links + CSS scroll-behavior:smooth (index.css)
// do the scroll-to-section natively — targets carry scroll-mt in App.
const links = [
  ["email", "Email"],
  ["photo", "Photo"],
  ["repo", "Repo"],
  ["dossier", "Dossier"],
  ["trap-lab", "Trap Lab"],
]

export default function Nav() {
  return (
    <nav className="sticky top-0 z-30 border-b border-line/30 bg-void/90 backdrop-blur-sm">
      <div className="max-w-2xl mx-auto flex items-center justify-between px-4 py-3">
        <a
          href="#top"
          className="font-display text-parchment text-base tracking-tight hover:text-redact transition-colors"
        >
          Eidolon
        </a>
        <ul className="flex items-center gap-4 sm:gap-6">
          {links.map(([id, label]) => (
            <li key={id}>
              <a
                href={`#${id}`}
                className="font-mono text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-parchment-dim hover:text-parchment transition-colors"
              >
                {label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
