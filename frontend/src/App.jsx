import { useState } from "react"
import EmailCheck from "./components/EmailCheck"
import PhotoCheck from "./components/PhotoCheck"
import RepoScan from "./components/RepoScan"
import Dossier from "./components/Dossier"

let nextId = 0

export default function App() {
  const [findings, setFindings] = useState([])

  function addFindings(newFindings) {
    setFindings((prev) => [
      ...prev,
      ...newFindings.map((f) => ({ ...f, id: nextId++ })),
    ])
  }

  return (
    <div className="min-h-screen px-4 py-10">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Your Eidolon</h1>
        <p className="text-gray-600 mb-8">
          See what can be discovered about you without your knowing. Run any check
          below — findings build up into a running dossier as they come in.
        </p>

        <div className="grid gap-4 mb-10">
          <EmailCheck onFindings={addFindings} />
          <PhotoCheck onFindings={addFindings} />
          <RepoScan onFindings={addFindings} />
        </div>

        <h2 className="text-lg font-semibold text-gray-900 mb-3">Dossier</h2>
        <Dossier findings={findings} />
      </div>
    </div>
  )
}
