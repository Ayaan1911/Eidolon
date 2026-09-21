import { useEffect, useState } from "react"
import { createTrap, getTrapAlerts } from "../services/api"
import { clearAdminToken, getAdminToken } from "../lib/adminAuth"
import AdminLogin from "./AdminLogin"
import SignalRow from "./SignalRow"
import Tag from "./Tag"
import ErrorNote from "./ErrorNote"

// Demo-mode stream. Every value is obviously a placeholder: RFC 5737 documentation
// IPs, a made-up country, and a fixed clock label instead of a real time.
const DEMO_ALERTS = [
  { id: 3, trap_id: "demo0003", ip: "203.0.113.7", location: "Sampleville, Exampleland", isp: "Example Broadband", org: "Example Networks Ltd", browser: "SampleBrowser", os: "DemoOS", referer: null, email: "visitor@example.com", password_attempted: true, password_length: 9, timestamp: "2000-01-01T00:03:00Z" },
  { id: 2, trap_id: "demo0002", ip: "198.51.100.23", location: "Placeholder City, Exampleland", isp: "Sample Telecom", org: null, browser: "SampleBrowser", os: "DemoOS", referer: "https://search.example/?q=placeholder", email: null, password_attempted: null, password_length: null, timestamp: "2000-01-01T00:02:00Z" },
  { id: 1, trap_id: "demo0001", ip: "192.0.2.14", location: "Nowhere, Exampleland", isp: "Example Broadband", org: "Example Networks Ltd", browser: "SampleBrowser", os: "DemoOS", referer: null, email: null, password_attempted: null, password_length: null, timestamp: "2000-01-01T00:01:00Z" },
]

// HH:MM:SS, 24h — the log timestamp.
function clock(ts) {
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? "--:--:--" : d.toLocaleTimeString([], { hour12: false })
}

function newestFirst(alerts) {
  return [...alerts].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
}

export default function TrapLab() {
  const [admin, setAdmin] = useState(() => getAdminToken() !== null)
  const [name, setName] = useState("")
  const [trap, setTrap] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  // The server rejected our token (expired, or ADMIN_KEY rotated): drop it and fall back to demo.
  function expireSession() {
    clearAdminToken()
    setAdmin(false)
    setAlerts(null)
    setTrap(null)
    setNotice("Admin session expired — back in demo mode.")
  }

  useEffect(() => {
    if (!admin) return
    getTrapAlerts()
      .then(setAlerts)
      .catch((err) => {
        if (err.status === 401) expireSession()
      })
  }, [admin])

  function handleLogin() {
    setNotice(null)
    setError(null)
    setTrap(null)
    setAdmin(true)
  }

  function handleLogout() {
    clearAdminToken()
    setAdmin(false)
    setAlerts(null)
    setTrap(null)
    setError(null)
  }

  async function handleCreate(e) {
    e.preventDefault()
    if (!admin) {
      // Demo mode: canned success, no request to the backend.
      setTrap({ demo: true, name: name.trim() })
      return
    }
    setLoading(true)
    setError(null)
    try {
      setTrap(await createTrap({ name }))
    } catch (err) {
      if (err.status === 401) expireSession()
      else setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function refreshAlerts() {
    setError(null)
    try {
      setAlerts(await getTrapAlerts())
    } catch (err) {
      if (err.status === 401) expireSession()
      else setError(err.message)
    }
  }

  const stream = admin ? (alerts ? newestFirst(alerts) : null) : DEMO_ALERTS

  return (
    <div className="border border-hairline bg-graphite px-5 py-5 max-w-2xl">
      {!admin && (
        <p className="mb-4 flex items-start gap-2 text-sm text-fg-dim">
          <Tag label="Demo mode" className="shrink-0 mt-0.5" />
          <span>Sample data only — nothing you do here is stored, deployed or logged.</span>
        </p>
      )}
      {notice && <p className="mb-4 text-sm text-fg-dim">{notice}</p>}

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

      {trap?.demo && (
        <p className="mt-3 flex items-start gap-2 text-sm text-fg-dim">
          <Tag label="Demo" className="shrink-0 mt-0.5" />
          <span>
            “{trap.name}” would be deployed here. This is a simulated trap — nothing was created.
          </span>
        </p>
      )}

      {trap && !trap.demo && (
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
            Signal stream{!admin && " · sample data"}
          </span>
          {admin && (
            <button
              onClick={refreshAlerts}
              className="font-mono text-[11px] uppercase tracking-[0.15em] text-fg-faint hover:text-fg"
            >
              Refresh →
            </button>
          )}
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
                <SignalRow key={a.id} alert={a} time={admin ? clock(a.timestamp) : "00:00:00"} />
              ))}
            </ul>
          )}
        </div>
      </div>

      <AdminLogin admin={admin} onLogin={handleLogin} onLogout={handleLogout} />
    </div>
  )
}
