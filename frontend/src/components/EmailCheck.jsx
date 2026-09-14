import { useState } from "react"
import { checkEmailExposure } from "../services/api"
import { emailToFindings } from "../lib/findings"

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
    <div className="border border-gray-200 rounded-lg p-4">
      <h2 className="font-semibold text-gray-900 mb-1">Email breach check</h2>
      <p className="text-sm text-gray-500 mb-3">
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
      {done && !error && (
        <p className="text-green-700 text-sm mt-3">Added to your dossier below ↓</p>
      )}
    </div>
  )
}
