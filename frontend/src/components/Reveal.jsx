import { useReveal } from "../lib/motion"

// Scroll-reveal wrapper. `delay` staggers siblings (ms).
export default function Reveal({ className = "", delay = 0, children }) {
  const ref = useReveal()
  return (
    <div
      ref={ref}
      className={`reveal ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  )
}
