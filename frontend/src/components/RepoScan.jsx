import { useState } from "react"
import { scanGithubRepos } from "../services/api"
import { repoToFindings } from "../lib/findings"
import FolderSection from "./FolderSection"

export default function RepoScan({ onFindings }) {
  const [username, setUsername] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const [incomplete, setIncomplete] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setDone(false)
    setIncomplete(null)
    try {
      const data = await scanGithubRepos(username)
      onFindings(repoToFindings(username, data))
      if (data.incomplete) setIncomplete(data.incomplete_reason)
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <FolderSection label="Repo">
      <h2 className="font-semibold text-ink mb-1">GitHub secret scan</h2>
      <p className="text-sm text-ink-soft mb-3">
        Scans your public, non-fork repos for accidentally committed API keys, tokens,
        and other credentials.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <input
          type="text"
          required
          value={username}
          onChange={(e) => {
            setUsername(e.target.value)
            setDone(false)
          }}
          placeholder="GitHub username"
          className="border border-line bg-paper px-4 py-2 text-ink placeholder:text-ink-soft/60 focus:outline-none focus:border-ink"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-ink text-paper-raised px-4 py-2 font-medium uppercase tracking-wide text-sm hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Scanning repos… this can take a bit" : "Scan my repos"}
        </button>
      </form>
      {error && <p className="text-redact text-sm mt-3">{error}</p>}
      {incomplete && (
        <p className="border-l-2 border-line pl-2 text-ink-soft text-sm italic mt-3">
          Scan incomplete: {incomplete}
        </p>
      )}
      {done && !error && (
        <p className="text-clear text-sm mt-3">Added to your dossier below ↓</p>
      )}
    </FolderSection>
  )
}
