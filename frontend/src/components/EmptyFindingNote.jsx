import Tag from "./Tag"

// A check that came back with nothing actionable (no breaches, no secrets, or
// a scan that was interrupted). Deliberately not FindingCard: there is no real
// finding_id behind this, so it must never offer a Trap/Decoy action.
export default function EmptyFindingNote({ finding, sourceLabel, status }) {
  return (
    <div className="py-4 flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <span className="block font-mono text-[10px] uppercase tracking-[0.18em] text-fg-faint mb-1.5">
          {sourceLabel}
        </span>
        <p className="text-fg-dim leading-relaxed">{finding.summary}</p>
      </div>
      <Tag label={status.label} tone={status.tone} className="shrink-0" />
    </div>
  )
}
