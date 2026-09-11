import { useState } from "react"
import { checkPhotoMetadata } from "../services/api"

function formatCapturedAt(raw) {
  if (!raw) return null
  const match = raw.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$/)
  if (!match) return raw
  const [, year, month, day, hour, minute] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute))
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
}

export default function PhotoCheck({ onBack }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  async function analyze(selected) {
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      setResult(await checkPhotoMetadata(selected))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) analyze(dropped)
  }

  function reset() {
    setResult(null)
    setError(null)
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="max-w-md w-full">
        <button onClick={onBack} className="text-sm text-gray-500 hover:text-gray-900 mb-4">
          ← Back
        </button>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Photo check</h1>
        <p className="text-gray-600 mb-6">
          Photos carry more than the image — device, timestamp, sometimes exact
          location. See what yours reveals.
        </p>

        {!result && (
          <label
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-lg py-10 px-4 cursor-pointer transition-colors ${
              dragOver ? "border-gray-900 bg-gray-50" : "border-gray-300"
            }`}
          >
            <span className="text-gray-600 text-sm">
              {loading ? "Analyzing..." : "Drop a photo here, or click to choose one"}
            </span>
            <input
              type="file"
              accept="image/*"
              className="hidden"
              disabled={loading}
              onChange={(e) => e.target.files?.[0] && analyze(e.target.files[0])}
            />
          </label>
        )}

        {error && <p className="text-red-600 text-sm mt-3">{error}</p>}

        {result && (
          <div className="flex flex-col gap-4">
            {result.has_location ? (
              <div className="border border-red-200 bg-red-50 rounded-lg p-4">
                <p className="text-red-700 font-semibold mb-1">⚠ Location found</p>
                <p className="text-gray-800 text-sm">
                  This photo reveals you were at{" "}
                  <span className="font-mono">
                    {result.latitude.toFixed(5)}, {result.longitude.toFixed(5)}
                  </span>
                  {result.captured_at && <> on {formatCapturedAt(result.captured_at)}</>}.
                </p>
                <a
                  href={`https://www.google.com/maps?q=${result.latitude},${result.longitude}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-red-700 underline mt-2 inline-block"
                >
                  View on map
                </a>
              </div>
            ) : (
              <div className="border border-green-200 bg-green-50 rounded-lg p-4">
                <p className="text-green-700 font-semibold mb-1">No location found</p>
                <p className="text-gray-700 text-sm">
                  This photo doesn't carry any GPS data — nothing here reveals where it
                  was taken.
                </p>
              </div>
            )}

            {(result.device || (result.captured_at && !result.has_location)) && (
              <div className="border border-gray-200 rounded-lg p-4 text-sm text-gray-600">
                {result.device && <p>Device: {result.device}</p>}
                {result.captured_at && !result.has_location && (
                  <p>Taken: {formatCapturedAt(result.captured_at)}</p>
                )}
              </div>
            )}

            <button
              onClick={reset}
              className="text-sm text-gray-500 hover:text-gray-900 self-start"
            >
              Check another photo
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
