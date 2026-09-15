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

// Severity as a rubber stamp (see Stamp / .stamp). tone only picks ink color.
const severityStamp = {
  CRITICAL: { label: "CRITICAL", tone: "critical" },
  HIGH: { label: "HIGH", tone: "high" },
  High: { label: "HIGH", tone: "high" },
  Medium: { label: "MEDIUM", tone: "neutral" },
  Low: { label: "LOW", tone: "neutral" },
  None: { label: "CLEAR", tone: "clear" },
}

export default function Dossier({ findings }) {
  if (findings.length === 0) {
    return (
      <div className="border border-dashed border-line/50 py-14 px-6 text-center text-parchment-dim italic">
        Run a check above to start uncovering your Eidolon.
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
          stamp={
            severityStamp[finding.severity] || {
              label: finding.severity || "—",
              tone: "neutral",
            }
          }
        />
      ))}
    </div>
  )
}
