import { useState } from "react"
import FindingCard from "./FindingCard"
import Eyebrow from "./Eyebrow"
import { useFindings } from "../context/FindingsContext"
import { getAdminToken } from "../lib/adminAuth"
import { getDefaultDossierFilter } from "../lib/prefs"

const sourceLabels = {
  breach: "Breach",
  photo: "Photo",
  secret: "Secret",
}

// Severity → Eidolon's own status vocabulary.
function statusOf(severity) {
  const s = (severity || "").toLowerCase()
  if (["critical", "high"].includes(s)) return { key: "escalated", label: "Escalated", tone: "strong" }
  if (["medium", "low"].includes(s)) return { key: "active", label: "Active", tone: "default" }
  return { key: "contained", label: "Contained", tone: "muted" }
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "escalated", label: "Escalated" },
  { key: "active", label: "Active" },
  { key: "contained", label: "Contained" },
]

export default function Dossier() {
  const { findings } = useFindings()
  const [filter, setFilter] = useState(getDefaultDossierFilter)
  // Read once per mount: Layout re-keys the route on every navigation (see
  // main key={pathname}), so this is fresh each time the Dossier is opened.
  const [isAdmin] = useState(() => getAdminToken() !== null)

  const withStatus = findings.map((f) => ({ ...f, status: statusOf(f.severity) }))
  const counts = withStatus.reduce(
    (acc, f) => ({ ...acc, all: acc.all + 1, [f.status.key]: (acc[f.status.key] || 0) + 1 }),
    { all: 0 }
  )
  const shown = filter === "all" ? withStatus : withStatus.filter((f) => f.status.key === filter)

  if (findings.length === 0) {
    return (
      <div className="border border-hairline bg-graphite py-16 px-6 text-center text-fg-dim">
        No findings yet. Run an Email, Photo or Repo check to start uncovering your Eidolon.
      </div>
    )
  }

  return (
    <div className="grid gap-8 md:grid-cols-[200px_1fr]">
      {/* Sidebar */}
      <aside className="md:border-r md:border-hairline md:pr-6">
        <Eyebrow className="mb-4">Filter</Eyebrow>
        <ul className="flex flex-row flex-wrap md:flex-col gap-1">
          {FILTERS.map((f) => {
            const active = filter === f.key
            const n = counts[f.key] || 0
            return (
              <li key={f.key}>
                <button
                  type="button"
                  onClick={() => setFilter(f.key)}
                  className={`w-full flex items-center justify-between gap-3 px-2.5 py-1.5 text-sm transition-colors ${
                    active ? "text-beacon" : "text-fg-dim hover:text-fg"
                  }`}
                >
                  <span>{f.label}</span>
                  <span className="font-mono text-[11px] text-fg-faint">
                    {String(n).padStart(2, "0")}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </aside>

      {/* List */}
      <div className="min-w-0 divide-y divide-hairline border-t border-hairline">
        {shown.length === 0 ? (
          <p className="py-8 text-sm text-fg-dim">Nothing under this status.</p>
        ) : (
          shown.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              sourceLabel={sourceLabels[finding.type] || finding.type}
              status={finding.status}
              isAdmin={isAdmin}
            />
          ))
        )}
      </div>
    </div>
  )
}
