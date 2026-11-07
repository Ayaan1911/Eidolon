import { useState } from "react"
import Eyebrow from "./Eyebrow"
import { getClientIpDiagnostics } from "../services/api"

// Admin-only. Shows what the server sees for this browser, to pick TRUSTED_PROXY_HOPS:
// the right value is the one where "Resolved IP" equals your real public IP.
export default function ClientIpCheck() {
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      setResult(await getClientIpDiagnostics())
    } catch (err) {
      setResult(null)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="mt-16">
      <Eyebrow className="mb-4">Client IP check</Eyebrow>
      <div className="border border-hairline bg-slate p-6 flex flex-col gap-4 max-w-xl">
        <p className="text-sm text-fg-dim leading-relaxed">
          Shows the address the server resolves for this browser. Compare it with your real public IP.
        </p>
        <div>
          <button
            type="button"
            onClick={run}
            disabled={loading}
            className="px-3.5 py-1.5 border border-hairline font-mono text-[10px] uppercase tracking-[0.15em] text-fg-dim hover:text-fg transition-colors"
          >
            {loading ? "Checking" : "Check"}
          </button>
        </div>
        {error && <p className="text-sm text-fg-dim">{error}</p>}
        {result && (
          <div className="font-mono text-xs text-fg flex flex-col gap-1.5">
            <p>Resolved IP: {result.resolved_ip}</p>
            <p>Socket peer: {result.socket_peer}</p>
            <p>Trusted proxy hops: {result.trusted_proxy_hops}</p>
            {Object.keys(result.headers).length === 0 && <p>No proxy headers received</p>}
            {Object.entries(result.headers).map(([name, value]) => (
              <p key={name} className="break-all">
                {name}: {value}
              </p>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
