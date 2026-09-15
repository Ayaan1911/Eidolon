// Sitewide status motif: a rubber-stamp badge (see .stamp in index.css).
// tone only picks the ink color; the stamped look is identical everywhere.
const toneClass = {
  critical: "text-redact",
  high: "text-redact",
  exposed: "text-redact",
  clear: "text-clear",
  deployed: "text-clear",
  neutral: "text-ink-soft",
}

export default function Stamp({ label, tone = "neutral", className = "" }) {
  return (
    <span className={`stamp ${toneClass[tone] || toneClass.neutral} ${className}`}>
      {label}
    </span>
  )
}
