import { useState } from "react"
import { checkPhotoMetadata } from "../services/api"
import { photoToFindings } from "../lib/findings"
import { useFindings } from "../context/FindingsContext"
import FolderSection from "./FolderSection"

function formatCapturedAt(raw) {
  if (!raw) return null
  const match = raw.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$/)
  if (!match) return raw
  const [, year, month, day, hour, minute] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute))
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
}

export default function PhotoCheck() {
  const { addFindings } = useFindings()
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
      addFindings(photoToFindings(data, formatCapturedAt))
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
    <FolderSection label="Photo">
      <label
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed py-8 px-4 cursor-pointer transition-colors ${
          dragOver ? "border-ink bg-paper" : "border-line"
        }`}
      >
        <span className="text-ink-soft text-sm">
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
      {error && <p className="text-redact text-sm mt-3">{error}</p>}
      {done && !error && (
        <p className="text-clear text-sm mt-3">
          Added to your dossier — view it under Dossier ↑
        </p>
      )}
    </FolderSection>
  )
}
