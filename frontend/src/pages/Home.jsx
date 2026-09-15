import { Link } from "react-router-dom"

const tools = [
  ["/email", "Email breach check", "Where your address has already leaked."],
  ["/photo", "Photo metadata check", "The device, time and place hidden in an image."],
  ["/repo", "GitHub secret scan", "Credentials left committed in public code."],
  ["/dossier", "Dossier", "Everything found so far, in one case file."],
  ["/trap-lab", "Trap Lab", "Turn the mirror around — bait a canary of your own."],
]

export default function Home() {
  return (
    <div>
      {/* The one lit lamp: a soft amber glow behind the wordmark only. */}
      <header className="relative border-b-2 border-double border-line/40 pb-8 mb-10 pt-8">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 h-72 w-[36rem] max-w-full"
          style={{
            background:
              "radial-gradient(closest-side, rgba(224,166,90,0.28), rgba(224,166,90,0.10) 45%, transparent 72%)",
          }}
        />
        <h1 className="relative font-display text-6xl sm:text-7xl text-parchment leading-[0.92] tracking-tight mb-4">
          Your Eidolon
        </h1>
        <p className="relative text-sm text-parchment-dim max-w-md leading-relaxed">
          See what can be discovered about you without your knowing — before
          someone else assembles it first. Run any check; findings build up into
          a running dossier.
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        {tools.map(([to, name, blurb]) => (
          <Link
            key={to}
            to={to}
            className="block border border-line bg-paper-raised px-4 py-3 hover:border-ink transition-colors"
          >
            <h2 className="font-display text-lg text-ink tracking-wide mb-1">{name}</h2>
            <p className="text-sm text-ink-soft">{blurb}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
