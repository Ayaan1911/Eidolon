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

// Eidolon's own tokens, documented in-universe as evidence tags.
const tokens = [
  { name: "Void", hex: "#17130F", role: "the page itself — the dark room the evidence sits in" },
  { name: "Paper", hex: "#F2EAD6", role: "every card surface, laid out under the lamp" },
  { name: "Ink", hex: "#241C13", role: "primary text, pressed into the paper" },
  { name: "Redact", hex: "#C63A2E", role: "the one accent — appears only as the stamp, never diluted" },
]

function FieldGuide() {
  return (
    <div>
      <Eyebrow className="mb-5">A Field Guide to Eidolon</Eyebrow>
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        {tokens.map((t) => (
          <div key={t.name} className="relative bg-paper-raised text-ink border border-line px-3 py-3">
            <span
              className="absolute top-2.5 right-2.5 w-2 h-2 rounded-full border border-ink-soft/50"
              aria-hidden
            />
            <span
              className="block w-full h-6 mb-2.5 border border-ink/15"
              style={{ background: t.hex }}
              aria-hidden
            />
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-display text-sm tracking-wide">{t.name}</span>
              <span className="font-mono text-[10px] text-ink-soft">{t.hex}</span>
            </div>
            <p className="font-mono text-[10px] leading-snug text-ink-soft mt-1.5">
              {t.role}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Footer() {
  return (
    <footer className="border-t border-line/20 mt-24 pt-14 pb-16">
      <div className="grid gap-10 sm:grid-cols-2 mb-14">
        <div>
          <Eyebrow className="mb-5">Tools</Eyebrow>
          <ul className="flex flex-col gap-2">
            {tools.map(([to, label]) => (
              <li key={to}>
                <Link
                  to={to}
                  className="font-sans text-sm text-parchment-dim hover:text-parchment transition-colors"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <Eyebrow className="mb-5">Project</Eyebrow>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="font-sans text-sm text-parchment-dim hover:text-parchment transition-colors"
          >
            Source on GitHub ↗
          </a>
        </div>
      </div>

      <FieldGuide />

      <p className="mt-12 font-mono text-[11px] tracking-wider text-parchment-dim/70">
        Eidolon — a mirror you point at yourself.
      </p>
    </footer>
  )
}
