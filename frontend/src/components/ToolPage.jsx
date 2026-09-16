import Eyebrow from "./Eyebrow"

// Shared frame for a single tool route: a quiet serif header above the tool.
export default function ToolPage({ title, intro, children }) {
  return (
    <div>
      <header className="mb-8 max-w-2xl">
        <Eyebrow className="mb-4">Eidolon</Eyebrow>
        <h1 className="font-serif text-4xl sm:text-5xl text-fg tracking-tight mb-4">
          {title}
        </h1>
        <p className="text-fg-dim leading-relaxed">{intro}</p>
      </header>
      {children}
    </div>
  )
}
