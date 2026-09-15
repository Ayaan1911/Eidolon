// Shared frame for a single tool route: a page-level intro block (on the dark
// background) above the tool's own form/card.
export default function ToolPage({ title, intro, children }) {
  return (
    <div>
      <header className="mb-8">
        <h1 className="font-display text-4xl text-parchment tracking-tight mb-3">
          {title}
        </h1>
        <p className="text-parchment-dim leading-relaxed max-w-xl">{intro}</p>
      </header>
      {children}
    </div>
  )
}
