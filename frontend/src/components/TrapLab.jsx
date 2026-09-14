import { useState } from "react"
import { createTrap, getTrapAlerts } from "../services/api"

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
      setTrap(await createTrap(name))
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
    <div className="border border-dashed border-purple-300 rounded-lg p-4">
      <h2 className="font-semibold text-gray-900 mb-1">Trap Lab (Phase 2 preview)</h2>
      <p className="text-sm text-gray-500 mb-3">
        Standalone test bed for the trap mechanism — not wired to the dossier yet.
      </p>

      <form onSubmit={handleCreate} className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Trap name"
          className="border border-gray-300 rounded-lg px-4 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-purple-600"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-purple-600 text-white rounded-lg px-4 py-2 font-medium disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create trap"}
        </button>
      </form>

      {error && <p className="text-red-600 text-sm mt-3">{error}</p>}

      {trap && (
        <div className="mt-3 text-sm">
          <p className="text-gray-600">
            Trap URL:{" "}
            <a
              href={trap.trap_url}
              target="_blank"
              rel="noreferrer"
              className="text-purple-700 underline font-mono"
            >
              {trap.trap_url}
            </a>
          </p>
        </div>
      )}

      <div className="mt-4">
        <button
          onClick={refreshAlerts}
          className="text-sm text-gray-500 hover:text-gray-900"
        >
          Refresh alerts →
        </button>

        {alerts && (
          <div className="flex flex-col gap-2 mt-3">
            {alerts.length === 0 ? (
              <p className="text-sm text-gray-500">No trap triggers logged yet.</p>
            ) : (
              alerts.map((a) => (
                <div key={a.id} className="border border-gray-200 rounded-lg p-3 text-sm">
                  <p className="text-gray-800">
                    {a.location} — {a.browser} on {a.os} ({a.device})
                  </p>
                  <p className="text-gray-500 font-mono text-xs mt-1">
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
