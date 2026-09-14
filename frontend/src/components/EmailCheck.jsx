import { useState } from "react"
import { checkEmailExposure } from "../services/api"
import { emailToFindings } from "../lib/findings"
import FolderSection from "./FolderSection"

export default function EmailCheck({ onFindings }) {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setDone(false)
    try {
      const data = await checkEmailExposure(email)
      onFindings(emailToFindings(email, data))
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <FolderSection label="Email">
      <h2 className="font-semibold text-ink mb-1">Email breach check</h2>
      <p className="text-sm text-ink-soft mb-3">
        See if your email has shown up in a known data breach.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            setDone(false)
          }}
          placeholder="you@example.com"
          className="border border-line bg-paper px-4 py-2 text-ink placeholder:text-ink-soft/60 focus:outline-none focus:border-ink"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-ink text-paper-raised px-4 py-2 font-medium uppercase tracking-wide text-sm hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Checking..." : "Check my exposure"}
        </button>
      </form>
      {error && <p className="text-redact text-sm mt-3">{error}</p>}
      {done && !error && (
        <p className="text-clear text-sm mt-3">Added to your dossier below ↓</p>
      )}
    </FolderSection>
  )
}
