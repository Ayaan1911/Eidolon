import Stamp from "./Stamp"
import { reasonFor } from "../lib/reasoning"

// "Why this is exposed" as an evidence-file entry: a stamped case note pasted
// into the finding, with a typed rationale and a redacted footer line. Not a
// gauge — the case-file language carries the explanation.
export default function ReasoningPanel({ finding, stamp }) {
  const { verdict, notes } = reasonFor(finding)
  const flagged = ["critical", "high"].includes((finding.severity || "").toLowerCase())

  return (
    <div className="mt-3 border border-ink/25 bg-paper">
      {/* Header — a solid bar carrying the verdict stamp. Red when flagged. */}
      <div
        className={`flex items-center justify-between gap-2 px-3 py-2 ${
          flagged ? "bg-redact text-parchment" : "bg-ink text-parchment"
        }`}
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.25em]">
          Case note — why this matters
        </span>
        <Stamp label={stamp.label} tone={stamp.tone} className="!text-parchment" />
      </div>

      <div className="px-4 py-3 font-mono text-[12px] leading-relaxed text-ink">
        <p className="flex items-center gap-2 mb-3">
          <span className="text-[10px] uppercase tracking-[0.2em] text-ink-soft">Verdict</span>
          <span className="font-display text-sm text-redact tracking-wide">{verdict}</span>
        </p>

        <ol className="flex flex-col gap-2.5">
          {notes.map((n, i) => (
            <li key={i} className="flex gap-3">
              <span className="text-redact font-bold shrink-0">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span>{n}</span>
            </li>
          ))}
        </ol>

        {/* Redacted footer line — solid bars, filed-under flavor. */}
        <p className="flex items-center gap-2 mt-4 pt-3 border-t border-ink/15 text-[10px] uppercase tracking-[0.2em] text-ink-soft">
          Filed under
          <span className="inline-block h-3 w-16 bg-ink align-middle" aria-hidden />
          <span className="inline-block h-3 w-10 bg-redact align-middle" aria-hidden />
          <span className="ml-auto">Eyes only</span>
        </p>
      </div>
    </div>
  )
}
