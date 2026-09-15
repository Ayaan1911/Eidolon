import { useState } from "react"
import { createTrap, getTrapAlerts } from "../services/api"
import Stamp from "./Stamp"

export default function TrapLab() {
  const [name, setName] = useState("")
  const [trap, setTrap] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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

      {error && <p className="text-redact text-sm mt-3">{error}</p>}

      {trap && (
        <div className="mt-3 text-sm">
          <p className="text-ink-soft flex items-center gap-2 flex-wrap">
            <Stamp label="DEPLOYED" tone="deployed" />
            <a
              href={trap.trap_url}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-ink underline decoration-line hover:text-redact"
            >
              {trap.trap_url}
            </a>
          </p>
        </div>
      )}

      <div className="mt-4">
        <button
          onClick={refreshAlerts}
          className="text-xs text-ink-soft hover:text-ink"
        >
          Refresh alerts →
        </button>

        {alerts && (
          <div className="flex flex-col gap-2 mt-3">
            {alerts.length === 0 ? (
              <p className="text-xs text-ink-soft">No trap triggers logged yet.</p>
            ) : (
              alerts.map((a) => (
                <div key={a.id} className="border border-line px-3 py-2 text-sm">
                  <p className="text-ink-soft">
                    {a.location} — {a.browser} on {a.os} ({a.device})
                  </p>
                  <p className="font-mono text-ink-soft text-xs mt-1">
                    {a.ip} · trap {a.trap_id} · {new Date(a.timestamp).toLocaleString()}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
