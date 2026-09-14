import { useState } from "react"
import EmailCheck from "./components/EmailCheck"
import PhotoCheck from "./components/PhotoCheck"
import RepoScan from "./components/RepoScan"
import Dossier from "./components/Dossier"
import TrapLab from "./components/TrapLab"

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
    <div className="min-h-screen font-sans px-4 py-10">
      <div className="max-w-2xl mx-auto">
        <header className="border-b-2 border-double border-line pb-4 mb-10">
          <h1 className="font-display text-3xl text-ink mb-2 tracking-tight">
            Your Eidolon
          </h1>
          <p className="text-ink-soft">
            See what can be discovered about you without your knowing. Run any check
            below — findings build up into a running dossier as they come in.
          </p>
        </header>

        <div className="flex flex-col gap-8 mb-12">
          <EmailCheck onFindings={addFindings} />
          <PhotoCheck onFindings={addFindings} />
          <RepoScan onFindings={addFindings} />
        </div>

        <h2 className="font-display text-xl text-ink tracking-wide mb-4">Dossier</h2>
        <Dossier findings={findings} />

        <div className="mt-14 mb-4 flex items-center gap-3">
          <span className="h-px flex-1 bg-line" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-ink-soft">
            Annex
          </span>
          <span className="h-px flex-1 bg-line" />
        </div>

        <TrapLab />
      </div>
    </div>
  )
}
