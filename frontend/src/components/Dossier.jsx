import FindingCard from "./FindingCard"

const sourceLabels = {
  breach: "Breach",
  photo: "Photo",
  secret: "Secret",
}

// Left-edge marker color — the redact accent is reserved for what's actually
// flagged; clean/lower findings stay in the neutral ink/line palette.
const severityAccent = {
  CRITICAL: "border-l-redact",
  HIGH: "border-l-redact",
  High: "border-l-redact",
  Medium: "border-l-ink-soft",
  Low: "border-l-line",
  None: "border-l-clear",
}

const severityBadge = {
  CRITICAL: { label: "CRITICAL", className: "bg-redact-soft text-redact border-redact/30" },
  HIGH: { label: "HIGH", className: "bg-redact-soft text-redact border-redact/30" },
  High: { label: "HIGH", className: "bg-redact-soft text-redact border-redact/30" },
  Medium: { label: "MEDIUM", className: "bg-transparent text-ink-soft border-line" },
  Low: { label: "LOW", className: "bg-transparent text-ink-soft border-line" },
  None: { label: "CLEAR", className: "bg-transparent text-clear border-clear/40" },
}

export default function Dossier({ findings }) {
  if (findings.length === 0) {
    return (
      <div className="border border-dashed border-line py-14 px-6 text-center text-ink-soft italic">
        Run a check below to start uncovering your Eidolon.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {findings.map((finding) => (
        <FindingCard
          key={finding.id}
          finding={finding}
          sourceLabel={sourceLabels[finding.type] || finding.type}
          accentClass={severityAccent[finding.severity] || "border-l-line"}
          badge={
            severityBadge[finding.severity] || {
              label: finding.severity || "—",
              className: "bg-transparent text-ink-soft border-line",
            }
          }
        />
      ))}
    </div>
  )
}
