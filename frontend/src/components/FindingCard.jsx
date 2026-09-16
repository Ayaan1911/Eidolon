import { useState } from "react"
import { createTrap } from "../services/api"
import Stamp from "./Stamp"
import ErrorNote from "./ErrorNote"
import ReasoningPanel from "./ReasoningPanel"

const trapTips = {
  secret:
    "Replace the exposed value at that file/line with this link disguised as a working credential — a scraper that tries to use it trips the trap instead.",
  breach:
    "Use this as a canary link anywhere you'd expect phishing aimed at that email to lead.",
}

// Renders a masked secret value ("AKIA...N7EX" or "****") as a censored
// document would: visible characters stay text, the hidden span becomes a
// solid ink bar instead of literal dots/asterisks.
function RedactedValue({ value }) {
  const dotsIndex = value.indexOf("...")
  if (dotsIndex === -1) {
    return (
      <span
        className="inline-block align-middle bg-ink h-[0.85em]"
        style={{ width: `${Math.min(Math.max(value.length, 4), 16) * 0.55}em` }}
        aria-label="redacted value"
      />
    )
  }
  return (
    <span className="align-middle">
      {value.slice(0, dotsIndex)}
      <span
        className="inline-block align-middle bg-ink h-[0.85em] w-6 mx-0.5"
        aria-hidden
      />
      {value.slice(dotsIndex + 3)}
    </span>
  )
}

export default function FindingCard({ finding, sourceLabel, accentClass, stamp }) {
  const [trap, setTrap] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [showReason, setShowReason] = useState(false)

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
    <div
      className={`border border-line border-l-2 ${accentClass} bg-paper-raised px-4 py-3 flex items-start gap-3`}
    >
      <div className="flex-1">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-mono text-[10px] uppercase tracking-wider border border-line px-1.5 py-0.5 text-ink-soft">
            {sourceLabel}
          </span>
          <Stamp label={stamp.label} tone={stamp.tone} />
        </div>

        <p className="text-ink mt-1">{finding.summary}</p>

        {finding.type === "secret" && finding.raw?.masked_value && (
          <p className="mt-2 text-xs text-ink-soft flex items-center gap-2">
            <Stamp label="EXPOSED" tone="exposed" />
            <span className="font-mono">
              <RedactedValue value={finding.raw.masked_value} />
            </span>
          </p>
        )}

        <div className="mt-2.5">
          <button
            type="button"
            onClick={() => setShowReason((v) => !v)}
            className="font-mono text-[11px] uppercase tracking-wider text-ink-soft hover:text-ink underline decoration-line hover:decoration-ink underline-offset-2"
          >
            {showReason ? "Hide case notes ↑" : "Why this matters →"}
          </button>
        </div>
        {showReason && <ReasoningPanel finding={finding} stamp={stamp} />}

        {trap && (
          <div className="mt-3 text-sm">
            <p className="text-ink-soft flex items-center gap-2 flex-wrap">
              <Stamp label="DEPLOYED" tone="deployed" />
              <button
                type="button"
                onClick={copyUrl}
                className="font-mono text-ink underline decoration-line hover:decoration-ink"
              >
                {trap.trap_url}
              </button>
              {copied && <span className="text-clear text-xs">Copied</span>}
            </p>
            <p className="text-ink-soft text-xs mt-1.5">{trapTips[finding.type]}</p>
          </div>
        )}
        {error && <ErrorNote>{error}</ErrorNote>}
      </div>

      {canTrap && !trap && (
        <button
          type="button"
          onClick={deployTrap}
          disabled={loading}
          className="text-xs font-medium border border-ink text-ink px-3 py-1 shrink-0 uppercase tracking-wide hover:bg-ink hover:text-paper-raised disabled:opacity-50"
        >
          {loading ? "Deploying..." : "Trap this →"}
        </button>
      )}
    </div>
  )
}
