import { useEffect, useState } from "react"
import { createTrap, getTrapAlerts } from "../services/api"
import Stamp from "./Stamp"
import ErrorNote from "./ErrorNote"

// HH:MM:SS, 24h — the log timestamp.
function clock(ts) {
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? "--:--:--" : d.toLocaleTimeString([], { hour12: false })
}

// Most recent first.
function newestFirst(alerts) {
  return [...alerts].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
}

export default function TrapLab() {
  const [name, setName] = useState("")
  const [trap, setTrap] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Pull the stream on open so it reads as live; stay silent if the backend
  // is down (a manual refresh surfaces the error instead).
  useEffect(() => {
    getTrapAlerts().then(setAlerts).catch(() => {})
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setTrap(await createTrap({ name }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function refreshAlerts() {
    setError(null)
    try {
      setAlerts(await getTrapAlerts())
    } catch (err) {
      setError(err.message)
    }
  }

  const stream = alerts ? newestFirst(alerts) : null

  return (
    <div className="border border-dashed border-line bg-paper-raised px-4 py-3">
      <form onSubmit={handleCreate} className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Trap name"
          className="border border-line bg-paper px-3 py-1.5 text-sm flex-1 text-ink placeholder:text-ink-soft/60 focus:outline-none focus:border-ink"
        />
        <button
          type="submit"
          disabled={loading}
          className="border border-ink text-ink px-3 py-1.5 text-sm font-medium uppercase tracking-wide hover:bg-ink hover:text-paper-raised disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create trap"}
        </button>
      </form>

      {error && <ErrorNote>{error}</ErrorNote>}

      {trap && (
        <div className="mt-3 text-sm">
          <p className="text-ink-soft flex items-center gap-2 flex-wrap">
            <Stamp label="DEPLOYED" tone="deployed" />
            <a
              href={trap.trap_url}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-ink underline decoration-line hover:decoration-ink"
            >
              {trap.trap_url}
            </a>
          </p>
        </div>
      )}

      {/* Signal stream — live trap-trigger log, newest at top. */}
      <div className="mt-5">
        <div className="flex items-center justify-between mb-2">
          <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-soft">
            <span className="live-dot" aria-hidden />
            Signal stream
          </span>
          <button
            onClick={refreshAlerts}
            className="font-mono text-[11px] uppercase tracking-wider text-ink-soft hover:text-ink"
          >
            Refresh →
          </button>
        </div>

        <div className="bg-void border border-line/25 font-mono text-xs">
          {stream === null ? (
            <p className="px-3 py-3 text-parchment-dim/70">connecting to stream…</p>
          ) : stream.length === 0 ? (
            <p className="px-3 py-3 text-parchment-dim/70">
              awaiting signal — no trap triggers logged yet.
            </p>
          ) : (
            <ul>
              {stream.map((a) => (
                <li
                  key={a.id}
                  className="flex gap-3 px-3 py-1.5 border-b border-line/10 last:border-0"
                >
                  <span className="text-clear shrink-0">{clock(a.timestamp)}</span>
                  <span className="text-parchment-dim truncate">
                    {a.location} · {a.browser}/{a.os} · {a.ip} · trap {a.trap_id}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
