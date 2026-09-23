import { useState } from "react"
import { createTrap, deployDecoy, deployTrapForFinding } from "../services/api"
import Tag from "./Tag"
import ErrorNote from "./ErrorNote"
import ReasoningPanel from "./ReasoningPanel"

const trapTips = {
  secret:
    "Replace the exposed value at that file/line with this link disguised as a working credential — a scraper that tries to use it trips the trap instead.",
  breach:
    "Use this as a canary link anywhere you'd expect phishing aimed at that email to lead.",
}

function clockTime(date) {
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
}

// A masked secret value ("AKIA...N7EX") shown as a censored line: visible
// characters stay text, the hidden span becomes a solid neutral block.
function RedactedValue({ value }) {
  const dotsIndex = value.indexOf("...")
  if (dotsIndex === -1) {
    return (
      <span
        className="inline-block align-middle bg-fg-faint h-[0.85em]"
        style={{ width: `${Math.min(Math.max(value.length, 4), 16) * 0.55}em` }}
        aria-label="redacted value"
      />
    )
  }
  return (
    <span className="align-middle">
      {value.slice(0, dotsIndex)}
      <span className="inline-block align-middle bg-fg-faint h-[0.85em] w-6 mx-0.5" aria-hidden />
      {value.slice(dotsIndex + 3)}
    </span>
  )
}

export default function FindingCard({ finding, sourceLabel, status, isAdmin }) {
  const [trap, setTrap] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [showReason, setShowReason] = useState(false)

  const [decoy, setDecoy] = useState(null)
  const [decoyLoading, setDecoyLoading] = useState(false)
  const [decoyError, setDecoyError] = useState(null)
  const [decoyCopied, setDecoyCopied] = useState(false)

  // Secret findings: a trap linked to the finding itself, rather than the
  // generic standalone one below. Seeded from the scan response so a trap
  // deployed earlier (found again on a rescan) already shows as deployed.
  const [findingTrap, setFindingTrap] = useState(finding.raw?.trap ?? null)
  const [findingTrapLoading, setFindingTrapLoading] = useState(false)
  const [findingTrapError, setFindingTrapError] = useState(null)

  const canTrap = finding.type === "breach"
  const canDeployDecoy = finding.type === "secret"
  const canDeployFindingTrap = finding.type === "secret" && isAdmin

  async function deployFindingTrap() {
    setFindingTrapLoading(true)
    setFindingTrapError(null)
    try {
      const { trap_url } = await deployTrapForFinding(finding.raw.id, {
        repo: finding.raw.repo,
        file: finding.raw.file,
        type: finding.raw.type,
      })
      setFindingTrap({ trap_url, hit_count: 0 })
    } catch (err) {
      setFindingTrapError(err.message)
    } finally {
      setFindingTrapLoading(false)
    }
  }

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
      // Clipboard unavailable — URL is still visible to copy manually.
    }
  }

  async function handleDeployDecoy() {
    setDecoyLoading(true)
    setDecoyError(null)
    try {
      const result = await deployDecoy(finding.id)
      setDecoy({ ...result, deployedAt: new Date() })
    } catch (err) {
      setDecoyError(err.message)
    } finally {
      setDecoyLoading(false)
    }
  }

  async function copyDecoy() {
    try {
      await navigator.clipboard.writeText(decoy.token)
      setDecoyCopied(true)
      setTimeout(() => setDecoyCopied(false), 1500)
    } catch {
      // Clipboard unavailable — key is still visible to copy manually.
    }
  }

  return (
    <div className="py-4 flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-1.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-fg-faint">
            {sourceLabel}
          </span>
          {finding.type === "secret" && finding.raw?.masked_value && (
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-fg-faint">
              Exposed
            </span>
          )}
        </div>

        <p className="text-fg leading-relaxed">{finding.summary}</p>

        {finding.type === "secret" && finding.raw?.masked_value && (
          <p className="mt-1.5 font-mono text-xs text-fg-dim">
            <RedactedValue value={finding.raw.masked_value} />
          </p>
        )}

        <div className="mt-2.5">
          <button
            type="button"
            onClick={() => setShowReason((v) => !v)}
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-fg-faint hover:text-fg transition-colors"
          >
            {showReason ? "Hide reasoning ↑" : "Why this matters →"}
          </button>
        </div>
        {showReason && <ReasoningPanel finding={finding} />}

        {trap && (
          <div className="mt-3 text-sm">
            <p className="flex items-center gap-2 flex-wrap text-fg-dim">
              <Tag label="Deployed" />
              <button
                type="button"
                onClick={copyUrl}
                className="font-mono text-fg underline decoration-hairline hover:decoration-edge"
              >
                {trap.trap_url}
              </button>
              {copied && <span className="text-fg-faint text-xs">Copied</span>}
            </p>
            <p className="text-fg-faint text-xs mt-1.5 leading-relaxed">{trapTips[finding.type]}</p>
          </div>
        )}
        {error && <ErrorNote>{error}</ErrorNote>}

        {decoy && (
          <div className="mt-3 text-sm">
            <p className="flex items-center gap-2 flex-wrap text-fg-dim">
              <Tag label={`Trap deployed · ${clockTime(decoy.deployedAt)}`} />
              <button
                type="button"
                onClick={copyDecoy}
                className="font-mono text-fg underline decoration-hairline hover:decoration-edge break-all"
              >
                {decoy.token}
              </button>
              {decoyCopied && <span className="text-fg-faint text-xs">Copied</span>}
            </p>
            <p className="text-fg-faint text-xs mt-1">
              Base URL: <span className="font-mono text-fg-dim">{decoy.base_url}</span>
            </p>
            <p className="text-fg-faint text-xs mt-1.5 leading-relaxed">
              This doesn't replace rotating or revoking the real secret — do that first.
              Then place this key and base URL in the exact spot the real one was. If
              someone already copied the real value before you rotated it, using this
              decoy is what catches them.
            </p>
          </div>
        )}
        {decoyError && <ErrorNote>{decoyError}</ErrorNote>}

        {findingTrap && (
          <div className="mt-3 text-sm">
            <p className="flex items-center gap-2 flex-wrap text-fg-dim">
              <Tag
                label={`Trap deployed · ${findingTrap.hit_count} hit${findingTrap.hit_count === 1 ? "" : "s"}`}
              />
              <a
                href={findingTrap.trap_url}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-fg underline decoration-hairline hover:decoration-edge"
              >
                {findingTrap.trap_url}
              </a>
            </p>
          </div>
        )}
        {findingTrapError && <ErrorNote>{findingTrapError}</ErrorNote>}
      </div>

      <div className="flex flex-col items-end gap-2.5 shrink-0">
        <Tag label={status.label} tone={status.tone} />
        {canTrap && !trap && (
          <button
            type="button"
            onClick={deployTrap}
            disabled={loading}
            className="rounded-full border border-hairline px-3 py-1 text-xs text-fg-dim hover:text-fg hover:border-edge disabled:opacity-50 transition-colors"
          >
            {loading ? "Deploying…" : "Trap this →"}
          </button>
        )}
        {canDeployFindingTrap && !findingTrap && (
          <button
            type="button"
            onClick={deployFindingTrap}
            disabled={findingTrapLoading}
            className="rounded-full border border-hairline px-3 py-1 text-xs text-fg-dim hover:text-fg hover:border-edge disabled:opacity-50 transition-colors"
          >
            {findingTrapLoading ? "Deploying…" : "Deploy trap →"}
          </button>
        )}
        {canDeployDecoy && !decoy && (
          <button
            type="button"
            onClick={handleDeployDecoy}
            disabled={decoyLoading}
            className="rounded-full border border-hairline px-3 py-1 text-xs text-fg-dim hover:text-fg hover:border-edge disabled:opacity-50 transition-colors"
          >
            {decoyLoading ? "Deploying…" : "Deploy a decoy →"}
          </button>
        )}
      </div>
    </div>
  )
}
