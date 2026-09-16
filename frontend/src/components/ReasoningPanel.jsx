import { reasonFor } from "../lib/reasoning"

// "Why this is exposed" — quiet. A hairline card, a serif headline with an
// italic accent, a monospace verdict line, and plain restrained prose. No
// stamps, no redaction bars, no "eyes only" costume.
export default function ReasoningPanel({ finding }) {
  const { verdict, notes } = reasonFor(finding)
  return (
    <div className="mt-3 border border-hairline bg-slate px-5 py-4">
      <h4 className="font-serif text-xl text-fg mb-1.5">
        Your exposure, <span className="italic">explained.</span>
      </h4>
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-dim mb-4">
        Verdict — {verdict}
      </p>
      <div className="flex flex-col gap-3 text-sm text-fg-dim leading-relaxed">
        {notes.map((n, i) => (
          <p key={i}>{n}</p>
        ))}
      </div>
    </div>
  )
}
