import { useEffect, useState } from "react"
import { createTrap, getTrapAlerts } from "../services/api"
import Tag from "./Tag"
import ErrorNote from "./ErrorNote"

// HH:MM:SS, 24h — the log timestamp.
function clock(ts) {
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? "--:--:--" : d.toLocaleTimeString([], { hour12: false })
}

function newestFirst(alerts) {
  return [...alerts].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
}

export default function TrapLab() {
  const [name, setName] = useState("")
  const [trap, setTrap] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
    <div className="border border-hairline bg-graphite px-5 py-5 max-w-2xl">
      <form onSubmit={handleCreate} className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Trap name"
          className="border border-hairline bg-slate px-4 py-2.5 text-sm flex-1 text-fg placeholder:text-fg-faint focus:outline-none focus:border-edge"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-beacon text-on-beacon px-5 py-2.5 text-sm font-medium hover:bg-beacon/90 disabled:opacity-50"
        >
          {loading ? "Creating…" : "Create trap"}
        </button>
      </form>

      {error && <ErrorNote>{error}</ErrorNote>}

      {trap && (
        <div className="mt-3 text-sm">
          <p className="flex items-center gap-2 flex-wrap text-fg-dim">
            <Tag label="Deployed" />
            <a
              href={trap.trap_url}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-fg underline decoration-hairline hover:decoration-edge"
            >
              {trap.trap_url}
            </a>
          </p>
        </div>
      )}

      {/* Signal stream — live trap-trigger log, newest at top. */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-2">
          <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-fg-dim">
            <span className="live-dot" aria-hidden />
            Signal stream
          </span>
          <button
            onClick={refreshAlerts}
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-fg-faint hover:text-fg"
          >
            Refresh →
          </button>
        </div>

        <div className="border border-hairline bg-obsidian font-mono text-xs">
          {stream === null ? (
            <p className="px-3 py-3 text-fg-faint">connecting to stream…</p>
          ) : stream.length === 0 ? (
            <p className="px-3 py-3 text-fg-faint">
              awaiting signal — no trap triggers logged yet.
            </p>
          ) : (
            <ul>
              {stream.map((a) => (
                <li
                  key={a.id}
                  className="flex gap-3 px-3 py-1.5 border-b border-hairline last:border-0"
                >
                  <span className="text-fg shrink-0">{clock(a.timestamp)}</span>
                  <span className="text-fg-dim truncate">
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
