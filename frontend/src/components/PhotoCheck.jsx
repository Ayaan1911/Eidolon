import { useState } from "react"
import { checkPhotoMetadata } from "../services/api"
import { photoToFindings } from "../lib/findings"

function formatCapturedAt(raw) {
  if (!raw) return null
  const match = raw.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$/)
  if (!match) return raw
  const [, year, month, day, hour, minute] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute))
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
}

export default function PhotoCheck({ onFindings }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [done, setDone] = useState(false)

  async function analyze(selected) {
    setError(null)
    setDone(false)
    setLoading(true)
    try {
      const data = await checkPhotoMetadata(selected)
      onFindings(photoToFindings(data, formatCapturedAt))
      setDone(true)
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

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <h2 className="font-semibold text-gray-900 mb-1">Photo metadata check</h2>
      <p className="text-sm text-gray-500 mb-3">
        Photos carry more than the image — device, timestamp, sometimes exact location.
      </p>
      <label
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-lg py-8 px-4 cursor-pointer transition-colors ${
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
      {error && <p className="text-red-600 text-sm mt-3">{error}</p>}
      {done && !error && (
        <p className="text-green-700 text-sm mt-3">Added to your dossier below ↓</p>
      )}
    </div>
  )
}
