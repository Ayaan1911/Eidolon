import { useState } from "react"
import { checkEmailExposure } from "../services/api"

export default function HomePage({ onResult, onCheckPhoto, onScanRepos }) {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const data = await checkEmailExposure(email)
      onResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="max-w-md w-full">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Eidolon</h1>
        <p className="text-gray-600 mb-6">
          See what can be discovered about you without your knowing.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-gray-900 text-white rounded-lg px-4 py-2 font-medium disabled:opacity-50"
          >
            {loading ? "Checking..." : "Check my exposure"}
          </button>
        </form>
        {error && <p className="text-red-600 text-sm mt-3">{error}</p>}

        <div className="flex flex-col gap-2 mt-6">
          <button
            onClick={onCheckPhoto}
            className="text-sm text-gray-500 hover:text-gray-900 text-left"
          >
            Or check a photo for hidden metadata →
          </button>
          <button
            onClick={onScanRepos}
            className="text-sm text-gray-500 hover:text-gray-900 text-left"
          >
            Or scan your GitHub repos for leaked secrets →
          </button>
        </div>
      </div>
    </div>
  )
}
