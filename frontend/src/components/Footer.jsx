import { Link } from "react-router-dom"
import Eyebrow from "./Eyebrow"

const REPO_URL = "https://github.com/Ayaan1911/Eidolon"

const tools = [
  ["/email", "Email breach check"],
  ["/photo", "Photo metadata check"],
  ["/repo", "GitHub secret scan"],
  ["/dossier", "Dossier"],
  ["/trap-lab", "Trap Lab"],
]

export default function Footer() {
  return (
    <footer className="border-t border-hairline mt-24 pt-12 pb-16">
      <div className="grid gap-10 sm:grid-cols-3 mb-12">
        <div>
          <Eyebrow className="mb-4">Tools</Eyebrow>
          <ul className="flex flex-col gap-2">
            {tools.map(([to, label]) => (
              <li key={to}>
                <Link
                  to={to}
                  className="text-sm text-fg-dim hover:text-fg transition-colors"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <Eyebrow className="mb-4">System</Eyebrow>
          <ul className="flex flex-col gap-2">
            <li>
              <Link to="/system" className="text-sm text-fg-dim hover:text-fg transition-colors">
                Design system &amp; settings
              </Link>
            </li>
            <li>
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-fg-dim hover:text-fg transition-colors"
              >
                Source on GitHub ↗
              </a>
            </li>
          </ul>
        </div>
        <div>
          <Eyebrow className="mb-4">Status</Eyebrow>
          <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-fg-dim">
            <span className="live-dot" aria-hidden />
            All systems quiet
          </p>
        </div>
      </div>

      <p className="font-mono text-[11px] tracking-wider text-fg-faint">
        Eidolon — a mirror you point at yourself.
      </p>
    </footer>
  )
}
