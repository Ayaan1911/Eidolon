import FindingCard from "./FindingCard"

const sourceLabels = {
  breach: "Breach",
  photo: "Photo",
  secret: "Secret",
}

const severityDot = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-red-500",
  High: "bg-red-500",
  Medium: "bg-amber-500",
  Low: "bg-gray-400",
  None: "bg-green-500",
}

export default function Dossier({ findings }) {
  if (findings.length === 0) {
    return (
      <div className="border border-dashed border-gray-300 rounded-lg py-14 px-6 text-center text-gray-500">
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
          severityDotClass={severityDot[finding.severity] || "bg-gray-400"}
        />
      ))}
    </div>
  )
}
