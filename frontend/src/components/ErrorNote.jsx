import Tag from "./Tag"

export default function ErrorNote({ children, className = "" }) {
  return (
    <p className={`mt-3 flex items-start gap-2 text-sm text-fg-dim ${className}`}>
      <Tag label="Error" className="shrink-0 mt-0.5" />
      <span>{children}</span>
    </p>
  )
}
