// Focal "signal card": a sparse monochrome scatter of your exposed surface
// among decoys. No glow, no shadow — the field is masked into a soft vignette
// so it dissolves into the card instead of sitting in a hard rectangle.
const COLS = 15
const ROWS = 11
const GAP = 22
const PAD = 18
const W = PAD * 2 + (COLS - 1) * GAP
const H = PAD * 2 + (ROWS - 1) * GAP

// Deterministic pseudo-random, so the field is stable between renders.
function field() {
  let seed = 20260916
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    return seed / 0x7fffffff
  }
  const dots = []
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const v = rnd()
      const kind = v > 0.975 ? "signal" : v > 0.9 ? "bright" : "decoy"
      dots.push({
        x: PAD + c * GAP + (rnd() - 0.5) * 5,
        y: PAD + r * GAP + (rnd() - 0.5) * 5,
        kind,
      })
    }
  }
  return dots
}

const DOTS = field()
const style = {
  signal: { r: 2.6, fill: "var(--color-beacon)", opacity: 1 },
  bright: { r: 1.8, fill: "var(--color-fg)", opacity: 0.55 },
  decoy: { r: 1.4, fill: "var(--color-fg-faint)", opacity: 0.4 },
}

export default function SignalCard() {
  const signals = DOTS.filter((d) => d.kind === "signal").length
  return (
    <div className="border border-hairline bg-graphite">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-fg-dim">
          Exposed surface
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-fg-faint">
          Decoy density
        </span>
      </div>
      <div
        className="px-2 py-2"
        style={{
          maskImage:
            "radial-gradient(120% 100% at 50% 45%, #000 55%, transparent 92%)",
          WebkitMaskImage:
            "radial-gradient(120% 100% at 50% 45%, #000 55%, transparent 92%)",
        }}
      >
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto block"
          role="img"
          aria-label="A scatter field of monochrome points representing exposed data among decoys"
        >
          {DOTS.map((d, i) => {
            const s = style[d.kind]
            return <circle key={i} cx={d.x} cy={d.y} r={s.r} fill={s.fill} opacity={s.opacity} />
          })}
        </svg>
      </div>
      <div className="flex items-center justify-between border-t border-hairline px-4 py-2.5">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-fg-faint">
          {String(signals).padStart(2, "0")} signals · {DOTS.length} points
        </span>
        <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-fg-dim">
          <span className="live-dot" aria-hidden />
          Watching
        </span>
      </div>
    </div>
  )
}
