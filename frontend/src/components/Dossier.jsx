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
        <div key={finding.id} className="border border-gray-200 rounded-lg p-4 flex items-start gap-3">
          <span
            className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${severityDot[finding.severity] || "bg-gray-400"}`}
            aria-hidden
          />
          <div className="flex-1">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
              {sourceLabels[finding.type] || finding.type}
            </span>
            <p className="text-gray-800 mt-0.5">{finding.summary}</p>
          </div>
          <button
            disabled
            title="Coming in Phase 2"
            className="text-xs text-gray-400 border border-gray-200 rounded-full px-3 py-1 shrink-0 cursor-not-allowed"
          >
            Trap this → <span className="text-gray-300">(Phase 2)</span>
          </button>
        </div>
      ))}
    </div>
  )
}
