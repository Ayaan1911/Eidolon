import { useState } from "react"
import { scanGithubRepos } from "../services/api"
import { repoToFindings } from "../lib/findings"

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
    <div className="border border-gray-200 rounded-lg p-4">
      <h2 className="font-semibold text-gray-900 mb-1">GitHub secret scan</h2>
      <p className="text-sm text-gray-500 mb-3">
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
          className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-gray-900 text-white rounded-lg px-4 py-2 font-medium disabled:opacity-50"
        >
          {loading ? "Scanning repos… this can take a bit" : "Scan my repos"}
        </button>
      </form>
      {error && <p className="text-red-600 text-sm mt-3">{error}</p>}
      {incomplete && (
        <p className="text-amber-700 text-sm mt-3">Scan incomplete: {incomplete}</p>
      )}
      {done && !error && (
        <p className="text-green-700 text-sm mt-3">Added to your dossier below ↓</p>
      )}
    </div>
  )
}
