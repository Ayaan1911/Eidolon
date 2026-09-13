import { useState } from "react"
import { scanGithubRepos } from "../services/api"

const severityStyles = {
  CRITICAL: "bg-red-100 text-red-700",
  HIGH: "bg-amber-100 text-amber-700",
}

export default function RepoScan({ onBack }) {
  const [username, setUsername] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await scanGithubRepos(username))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setResult(null)
    setError(null)
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-10">
      <div className="max-w-lg w-full">
        <button onClick={onBack} className="text-sm text-gray-500 hover:text-gray-900 mb-4">
          ← Back
        </button>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Repo secret scan</h1>
        <p className="text-gray-600 mb-6">
          Scans your public, non-fork repositories for accidentally committed API
          keys, tokens, and other credentials — the same mistakes that leak real
          secrets every day.
        </p>

        {!result && (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
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
        )}

        {error && <p className="text-red-600 text-sm mt-3">{error}</p>}

        {result && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>
                Scanned {result.repos_scanned} recently updated repo
                {result.repos_scanned === 1 ? "" : "s"} for @{result.username}
              </span>
              <button onClick={reset} className="text-gray-500 hover:text-gray-900">
                Scan another
              </button>
            </div>

            {result.incomplete && (
              <div className="border border-amber-200 bg-amber-50 rounded-lg p-3 text-sm text-amber-800">
                Scan incomplete: {result.incomplete_reason}
              </div>
            )}

            {result.total_findings === 0 ? (
              <div className="border border-green-200 bg-green-50 rounded-lg p-4 text-sm text-green-700">
                No exposed secrets found in the last {result.repos_scanned} updated
                repos.
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {result.results.map((repo) => (
                  <div key={repo.repo} className="border border-gray-200 rounded-lg p-4">
                    <h2 className="font-semibold text-gray-900 mb-2">{repo.repo}</h2>
                    <div className="flex flex-col gap-2">
                      {repo.findings.map((f, i) => (
                        <div
                          key={i}
                          className="flex items-start justify-between gap-3 text-sm border-t border-gray-100 pt-2 first:border-0 first:pt-0"
                        >
                          <div>
                            <p className="text-gray-800">
                              {f.file}:{f.line}
                            </p>
                            <p className="text-gray-500">
                              {f.type} — <span className="font-mono">{f.masked_value}</span>
                            </p>
                          </div>
                          <span
                            className={`text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap ${
                              severityStyles[f.severity] || "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {f.severity}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
