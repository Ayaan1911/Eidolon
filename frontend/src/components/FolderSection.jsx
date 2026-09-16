// Quiet hairline-bordered card with a mono section label (the case-file
// folder-tab is retired).
export default function FolderSection({ label, children }) {
  return (
    <section className="border border-hairline bg-graphite max-w-2xl">
      <div className="border-b border-hairline px-4 py-2.5">
        <span className="font-mono text-[11px] uppercase tracking-[0.25em] text-fg-faint">
          {label}
        </span>
      </div>
      <div className="px-4 py-4">{children}</div>
    </section>
  )
}
