import { useState } from "react"
import { adminLogin } from "../services/api"
import { setAdminToken } from "../lib/adminAuth"

const linkClass =
  "font-mono text-[11px] uppercase tracking-[0.15em] text-fg-faint hover:text-fg transition-colors"

// Deliberately quiet: a faint "Admin" link that expands into a passphrase field.
// A failed login only ever says "Access denied" — the server gives no reason either.
export default function AdminLogin({ admin, onLogin, onLogout }) {
  const [open, setOpen] = useState(false)
  const [passphrase, setPassphrase] = useState("")
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)

  if (admin) {
    return (
      <button type="button" onClick={onLogout} className={linkClass}>
        Admin · sign out
      </button>
    )
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={linkClass}>
        Admin
      </button>
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setFailed(false)
    try {
      const { token } = await adminLogin(passphrase)
      setAdminToken(token)
      setPassphrase("")
      setOpen(false)
      onLogin()
    } catch {
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 flex-wrap">
      <input
        type="password"
        autoComplete="off"
        autoFocus
        required
        value={passphrase}
        onChange={(e) => setPassphrase(e.target.value)}
        placeholder="Passphrase"
        aria-label="Admin passphrase"
        className="border border-hairline bg-slate px-3 py-1.5 text-xs text-fg placeholder:text-fg-faint focus:outline-none focus:border-edge"
      />
      <button type="submit" disabled={loading} className={`${linkClass} disabled:opacity-50`}>
        {loading ? "…" : "Enter →"}
      </button>
      <button type="button" onClick={() => setOpen(false)} className={linkClass}>
        Cancel
      </button>
      {failed && <span className="text-xs text-fg-dim">Access denied.</span>}
    </form>
  )
}
