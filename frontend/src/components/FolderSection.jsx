export default function FolderSection({ label, children }) {
  return (
    <section className="relative mt-4">
      <span className="absolute -top-3 left-4 bg-paper-raised border border-line border-b-0 px-3 py-1 font-display text-[11px] uppercase tracking-[0.2em] text-ink-soft">
        {label}
      </span>
      <div className="border border-line bg-paper-raised px-4 pt-6 pb-4">{children}</div>
    </section>
  )
}
