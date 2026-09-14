import { useState } from "react"
import { createTrap } from "../services/api"

const trapTips = {
  secret:
    "Replace the exposed value at that file/line with this link disguised as a working credential — a scraper that tries to use it trips the trap instead.",
  breach:
    "Use this as a canary link anywhere you'd expect phishing aimed at that email to lead.",
}

export default function FindingCard({ finding, sourceLabel, severityDotClass }) {
  const [trap, setTrap] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  const canTrap = finding.type === "breach" || finding.type === "secret"

  async function deployTrap() {
    setLoading(true)
    setError(null)
    try {
      const label = finding.type === "breach" ? "Breach" : "Secret"
      setTrap(
        await createTrap({
          name: `${label} canary — ${finding.summary}`,
          source_type: finding.type,
          context: finding.summary,
        })
      )
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(trap.trap_url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard API unavailable (e.g. insecure context) — URL is still visible to copy manually.
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4 flex items-start gap-3">
      <span
        className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${severityDotClass}`}
        aria-hidden
      />
      <div className="flex-1">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
          {sourceLabel}
        </span>
        <p className="text-gray-800 mt-0.5">{finding.summary}</p>

        {trap && (
          <div className="mt-2 text-sm">
            <p className="text-gray-600">
              Trap deployed:{" "}
              <button
                type="button"
                onClick={copyUrl}
                className="text-purple-700 underline font-mono"
              >
                {trap.trap_url}
              </button>
              {copied && <span className="text-green-600 text-xs ml-2">Copied</span>}
            </p>
            <p className="text-gray-500 text-xs mt-1">{trapTips[finding.type]}</p>
          </div>
        )}
        {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
      </div>

      {canTrap && !trap && (
        <button
          type="button"
          onClick={deployTrap}
          disabled={loading}
          className="text-xs text-purple-700 border border-purple-200 rounded-full px-3 py-1 shrink-0 hover:bg-purple-50 disabled:opacity-50"
        >
          {loading ? "Deploying..." : "Trap this →"}
        </button>
      )}
    </div>
  )
}
