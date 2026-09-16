import { useState } from "react"
import Eyebrow from "./Eyebrow"
import { SystemGrid } from "../lib/systemCards"
import { getReduceMotion, setReduceMotion, getDefaultDossierFilter, setDefaultDossierFilter } from "../lib/prefs"

const tokens = [
  { name: "--color-obsidian", value: "#0d0d0f", swatch: true },
  { name: "--color-graphite", value: "#151517", swatch: true },
  { name: "--color-slate", value: "#1c1c1f", swatch: true },
  { name: "--color-hairline", value: "#2a2a2e", swatch: true },
  { name: "--color-edge", value: "#3a3a40", swatch: true },
  { name: "--color-fg", value: "#d7d5d0", swatch: true },
  { name: "--color-fg-dim", value: "#96958f", swatch: true },
  { name: "--color-fg-faint", value: "#66655f", swatch: true },
  { name: "--color-beacon", value: "#e9e2d0", swatch: true },
  { name: "--color-on-beacon", value: "#14130f", swatch: true },
  { name: "--font-serif", value: "Fraunces" },
  { name: "--font-sans", value: "Inter" },
  { name: "--font-mono", value: "IBM Plex Mono" },
]

const filterOptions = [
  { key: "all", label: "All" },
  { key: "escalated", label: "Escalated" },
  { key: "active", label: "Active" },
  { key: "contained", label: "Contained" },
]

const changelog = [
  { build: "2026.09", note: "Full monochrome identity — three surface tiers, one beacon accent, hairlines only." },
  { build: "2026.09", note: "Reasoning panel restyled quiet. The stamped case-file costume is gone; the explanation stayed." },
  { build: "2026.09", note: "Dossier rebuilt as a sidebar and hairline-divided list, with Active / Contained / Escalated status." },
  { build: "2026.08", note: "Landing narrative rebuilt around Mirror, Dossier, Trap and System." },
  { build: "2026.08", note: "Routed pages split out; findings now persist across navigation." },
]

export default function System() {
  const [reduceMotion, setReduceMotionState] = useState(getReduceMotion)
  const [defaultFilter, setDefaultFilterState] = useState(getDefaultDossierFilter)

  function toggleMotion() {
    const next = !reduceMotion
    setReduceMotion(next)
    setReduceMotionState(next)
  }

  function chooseFilter(key) {
    setDefaultDossierFilter(key)
    setDefaultFilterState(key)
  }

  return (
    <div>
      <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-fg-dim mb-10">
        <span className="live-dot" aria-hidden />
        All systems quiet
      </p>

      <SystemGrid />

      {/* Preferences — the Atlas controls pattern. */}
      <section className="mt-16">
        <Eyebrow className="mb-4">Preferences</Eyebrow>
        <div className="border border-hairline bg-slate p-6 flex flex-col gap-6 max-w-xl">
          <label className="flex items-center gap-3 text-sm text-fg cursor-pointer">
            <input
              type="checkbox"
              checked={reduceMotion}
              onChange={toggleMotion}
              className="h-4 w-4 accent-beacon border border-hairline"
            />
            Reduce motion
          </label>

          <div>
            <p className="text-sm text-fg mb-2.5">Default dossier filter</p>
            <div className="inline-flex border border-hairline">
              {filterOptions.map((f, i) => {
                const active = defaultFilter === f.key
                return (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => chooseFilter(f.key)}
                    className={`px-3.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] transition-colors ${
                      i > 0 ? "border-l border-hairline" : ""
                    } ${active ? "bg-beacon text-on-beacon" : "text-fg-dim hover:text-fg"}`}
                  >
                    {f.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </section>

      {/* Token panel */}
      <section className="mt-16">
        <Eyebrow className="mb-4">Tokens</Eyebrow>
        <div className="border border-hairline bg-graphite divide-y divide-hairline max-w-xl">
          {tokens.map((t) => (
            <div key={t.name} className="flex items-center justify-between gap-4 px-4 py-2.5">
              <span className="font-mono text-xs text-fg-dim">{t.name}</span>
              <span className="flex items-center gap-2 font-mono text-xs text-fg">
                {t.swatch && (
                  <span className="h-3 w-3 border border-hairline shrink-0" style={{ background: t.value }} />
                )}
                {t.value}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Changelog */}
      <section className="mt-16 mb-4">
        <Eyebrow className="mb-4">Changelog</Eyebrow>
        <div className="border border-hairline bg-graphite divide-y divide-hairline max-w-xl">
          {changelog.map((c, i) => (
            <div key={i} className="flex items-start gap-4 px-4 py-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-fg-faint shrink-0 pt-0.5">
                {c.build}
              </span>
              <p className="text-sm text-fg-dim leading-relaxed">{c.note}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
