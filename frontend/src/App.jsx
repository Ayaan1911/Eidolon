import { useState } from "react"
import Nav from "./components/Nav"
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
    <div id="top" className="min-h-screen font-sans">
      <Nav />

      <div className="max-w-2xl mx-auto px-4 pb-16">
        {/* Hero — the one lit lamp: a soft amber glow behind the title only. */}
        <header className="relative border-b-2 border-double border-line/40 pb-8 mb-12 pt-14">
          <div
            aria-hidden
            className="pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 h-72 w-[36rem] max-w-full"
            style={{
              background:
                "radial-gradient(closest-side, rgba(224,166,90,0.28), rgba(224,166,90,0.10) 45%, transparent 72%)",
            }}
          />
          <h1 className="relative font-display text-6xl sm:text-7xl text-parchment leading-[0.92] tracking-tight mb-4">
            Your Eidolon
          </h1>
          <p className="relative text-sm text-parchment-dim max-w-md leading-relaxed">
            See what can be discovered about you without your knowing. Run any check
            below — findings build up into a running dossier as they come in.
          </p>
        </header>

        <div className="flex flex-col gap-8 mb-14">
          <div id="email" className="scroll-mt-20">
            <EmailCheck onFindings={addFindings} />
          </div>
          <div id="photo" className="scroll-mt-20">
            <PhotoCheck onFindings={addFindings} />
          </div>
          <div id="repo" className="scroll-mt-20">
            <RepoScan onFindings={addFindings} />
          </div>
        </div>

        <h2
          id="dossier"
          className="scroll-mt-20 font-display text-2xl text-parchment tracking-wide mb-5"
        >
          Dossier
        </h2>
        <Dossier findings={findings} />

        <div id="trap-lab" className="scroll-mt-20 mt-16 mb-5 flex items-center gap-3">
          <span className="h-px flex-1 bg-line/40" />
          <span className="font-display text-[11px] uppercase tracking-[0.2em] text-parchment-dim">
            Annex
          </span>
          <span className="h-px flex-1 bg-line/40" />
        </div>

        <TrapLab />
      </div>
    </div>
  )
}
