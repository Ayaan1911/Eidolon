// Eidolon's own design tokens, explained — shared by the Home "System"
// section and the /system page so the two never drift apart.
export const systemCards = [
  {
    label: "Surfaces",
    title: "Three tiers, by value",
    body: "Obsidian, graphite, slate — stepped in small value increments, never by hue. Depth without decoration.",
    sample: (
      <div className="flex gap-2">
        {[
          ["Obsidian", "#0d0d0f"],
          ["Graphite", "#151517"],
          ["Slate", "#1c1c1f"],
        ].map(([n, hex]) => (
          <div key={n} className="flex-1">
            <div className="h-10 border border-hairline" style={{ background: hex }} />
            <p className="mt-1.5 font-mono text-[9px] uppercase tracking-wider text-fg-faint">{n}</p>
          </div>
        ))}
      </div>
    ),
  },
  {
    label: "Separation",
    title: "Hairlines only",
    body: "Every division is a single 1px hairline. Zero shadows, zero fills doing a border's job.",
    sample: (
      <div className="space-y-3">
        <div className="border-t border-hairline" />
        <div className="border-t border-edge" />
        <p className="font-mono text-[9px] uppercase tracking-wider text-fg-faint">hairline · edge</p>
      </div>
    ),
  },
  {
    label: "Accent",
    title: "One quiet beacon",
    body: "A single warm off-white, spent only on primary actions, focus rings, and one active state. Nothing else is colored.",
    sample: (
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 border border-hairline" style={{ background: "#e9e2d0" }} />
        <span className="font-mono text-[10px] uppercase tracking-wider text-fg-dim">#E9E2D0 · Beacon</span>
      </div>
    ),
  },
  {
    label: "Type",
    title: "Serif · sans · mono",
    body: "Fraunces for display with an italic accent, Inter for body and UI, IBM Plex Mono for tokens and status.",
    sample: (
      <div className="flex items-baseline gap-4">
        <span className="font-serif text-2xl text-fg">Aa</span>
        <span className="font-sans text-2xl text-fg">Aa</span>
        <span className="font-mono text-2xl text-fg">Aa</span>
      </div>
    ),
  },
  {
    label: "Signal",
    title: "The scatter field",
    body: "A masked monochrome dot-field standing in for exposed surface among decoys — the one figurative device, kept quiet.",
    sample: (
      <div className="flex flex-wrap gap-1.5 max-w-[8rem]">
        {Array.from({ length: 24 }).map((_, i) => (
          <span
            key={i}
            className={`h-1.5 w-1.5 rounded-full ${i === 5 || i === 17 ? "bg-beacon" : "bg-fg-faint/50"}`}
          />
        ))}
      </div>
    ),
  },
  {
    label: "Access",
    title: "Legible by default",
    body: "Beacon focus rings on every control, honoured reduced-motion, and contrast that never leans on color to carry meaning.",
    sample: (
      <div className="inline-flex items-center gap-2 border border-beacon px-3 py-1.5">
        <span className="font-mono text-[10px] uppercase tracking-wider text-fg">Focus ring</span>
      </div>
    ),
  },
]

export function SystemGrid() {
  return (
    <div className="grid gap-px bg-hairline border border-hairline sm:grid-cols-2 lg:grid-cols-3">
      {systemCards.map((c) => (
        <div key={c.label} className="bg-graphite p-6 flex flex-col">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-fg-faint mb-3">
            {c.label}
          </p>
          <h3 className="font-serif text-xl text-fg mb-2.5">{c.title}</h3>
          <p className="text-sm text-fg-dim leading-relaxed mb-5">{c.body}</p>
          <div className="mt-auto">{c.sample}</div>
        </div>
      ))}
    </div>
  )
}
