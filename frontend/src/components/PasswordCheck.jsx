import { useState } from "react"
import { pwnedCount } from "../lib/pwned"
import FolderSection from "./FolderSection"
import ErrorNote from "./ErrorNote"

// The password never leaves this browser tab: pwnedCount sends only a 5-character
// hash prefix to the Pwned Passwords range API. Nothing is stored, and no Eidolon server is involved.
export default function PasswordCheck() {
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [count, setCount] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setCount(null)
    try {
      setCount(await pwnedCount(password))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <FolderSection label="Password">
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <input
          type="password"
          required
          autoComplete="off"
          aria-label="Password to check"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value)
            setCount(null)
          }}
          className="border border-hairline bg-slate px-4 py-2.5 text-fg focus:outline-none focus:border-edge"
        />
        <button
          type="submit"
          disabled={loading}
          className="self-start rounded-full bg-beacon text-on-beacon px-5 py-2.5 text-sm font-medium hover:bg-beacon/90 disabled:opacity-50"
        >
          {loading ? "Checking..." : "Check against known breaches"}
        </button>
      </form>
      {error && <ErrorNote>{error}</ErrorNote>}
      {count !== null && !error && (
        <p className="text-fg-dim text-sm mt-3" role="status">
          {count > 0
            ? `This password appears ${count.toLocaleString()} times in known breaches. Anyone trying leaked passwords will try it early; stop using it everywhere.`
            : "Not found in known breaches. That is not proof it is strong, only that it has not leaked in the data this service holds."}
        </p>
      )}
      <p className="text-fg-faint text-xs mt-3">
        Your password stays in this browser. Only the first 5 characters of its SHA-1 hash are sent
        to Have I Been Pwned; the match is made here.
      </p>
    </FolderSection>
  )
}
