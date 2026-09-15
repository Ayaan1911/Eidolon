import { useState } from "react"
import { scanGithubRepos } from "../services/api"
import { repoToFindings } from "../lib/findings"
import { useFindings } from "../context/FindingsContext"
import FolderSection from "./FolderSection"
import ErrorNote from "./ErrorNote"

export default function RepoScan() {
  const { addFindings } = useFindings()
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
      addFindings(repoToFindings(username, data))
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
      {error && <ErrorNote>{error}</ErrorNote>}
      {incomplete && (
        <p className="border-l-2 border-line pl-2 text-ink-soft text-sm italic mt-3">
          Scan incomplete: {incomplete}
        </p>
      )}
      {done && !error && (
        <p className="text-clear text-sm mt-3">
          Added to your dossier — view it under Dossier ↑
        </p>
      )}
    </FolderSection>
  )
}
