// Quiet monochrome status/label tag — small tracked mono caps inside a
// hairline. tone only steps value; there is no colored variant.
const tones = {
  muted: "text-fg-faint border-hairline",
  default: "text-fg-dim border-hairline",
  strong: "text-fg border-edge",
}

export default function Tag({ label, tone = "default", className = "" }) {
  return (
    <span
      className={`inline-block font-mono text-[10px] uppercase tracking-[0.18em] leading-none px-1.5 py-1 border ${
        tones[tone] || tones.default
      } ${className}`}
    >
      {label}
    </span>
  )
}
