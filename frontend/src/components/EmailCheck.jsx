import { useState } from "react"
import { checkEmailExposure } from "../services/api"
import { emailToFindings } from "../lib/findings"
import { useFindings } from "../context/FindingsContext"
import FolderSection from "./FolderSection"
import ErrorNote from "./ErrorNote"

export default function EmailCheck() {
  const { addFindings } = useFindings()
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
      addFindings(emailToFindings(email, data))
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <FolderSection label="Email">
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
          className="border border-hairline bg-slate px-4 py-2.5 text-fg placeholder:text-fg-faint focus:outline-none focus:border-edge"
        />
        <button
          type="submit"
          disabled={loading}
          className="self-start rounded-full bg-beacon text-on-beacon px-5 py-2.5 text-sm font-medium hover:bg-beacon/90 disabled:opacity-50"
        >
          {loading ? "Checking..." : "Check my exposure"}
        </button>
      </form>
      {error && <ErrorNote>{error}</ErrorNote>}
      {done && !error && (
        <p className="text-fg-dim text-sm mt-3">
          Added to your dossier — view it under Dossier ↑
        </p>
      )}
    </FolderSection>
  )
}
