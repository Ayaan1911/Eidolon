import { useState } from "react"
import { adminLogin } from "../services/api"
import { setAdminToken } from "../lib/adminAuth"

const linkClass =
  "font-mono text-[11px] uppercase tracking-[0.15em] text-fg-faint hover:text-fg transition-colors"

// A 401 always reads the same, whatever the reason; other failures say so
// plainly so a dead backend isn't mistaken for a wrong passphrase.
function failureMessage(err) {
  if (err.status === 401) return "Incorrect passphrase."
  if (err.status === 429) return "Too many attempts — wait a minute and try again."
  return "Couldn't reach the sign-in service. Try again."
}

// Quiet by default: a faint "Admin" link that opens a labelled passphrase row.
export default function AdminLogin({ admin, onLogin, onLogout }) {
  const [open, setOpen] = useState(false)
  const [passphrase, setPassphrase] = useState("")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)

  if (admin || !open) {
    return (
      <div className="mt-6 flex justify-end">
        <button type="button" onClick={admin ? onLogout : () => setOpen(true)} className={linkClass}>
          {admin ? "Admin · sign out" : "Admin"}
        </button>
      </div>
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    try {
      const { token } = await adminLogin(passphrase)
      setAdminToken(token)
      setPassphrase("")
      setOpen(false)
      onLogin()
    } catch (err) {
      setMessage(failureMessage(err))
    } finally {
      setLoading(false)
    }
  }

  function handleCancel() {
    setOpen(false)
    setPassphrase("")
    setMessage(null)
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 border-t border-hairline pt-4">
      <label htmlFor="admin-passphrase" className="block font-mono text-[11px] uppercase tracking-[0.2em] text-fg-dim mb-2">
        Admin sign-in
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="admin-passphrase"
          type="password"
          autoComplete="off"
          autoFocus
          required
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          placeholder="Passphrase"
          className="border border-hairline bg-slate px-4 py-2.5 text-sm flex-1 text-fg placeholder:text-fg-faint focus:outline-none focus:border-edge"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full border border-edge text-fg px-5 py-2.5 text-sm font-medium hover:bg-slate disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <button type="button" onClick={handleCancel} className="px-2 text-sm text-fg-dim hover:text-fg">
          Cancel
        </button>
      </div>
      {message && (
        <p role="alert" className="mt-2 text-sm text-fg-dim">
          {message}
        </p>
      )}
    </form>
  )
}
