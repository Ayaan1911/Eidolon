import { useEffect, useRef } from "react"

const reduced =
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

// Adds `is-visible` (see .reveal in index.css) when the element scrolls into
// view. Reduced-motion or no IntersectionObserver → visible immediately.
export function useReveal() {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (reduced || typeof IntersectionObserver === "undefined") {
      el.classList.add("is-visible")
      return
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("is-visible")
          io.disconnect()
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

// Pulls the element toward the cursor while hovered (magnetic CTA). No-op
// under reduced-motion.
export function useMagnetic(strength = 0.25) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el || reduced) return
    function move(e) {
      const r = el.getBoundingClientRect()
      el.style.transform = `translate(${(e.clientX - (r.left + r.width / 2)) * strength}px, ${
        (e.clientY - (r.top + r.height / 2)) * strength
      }px)`
    }
    function reset() {
      el.style.transform = ""
    }
    el.addEventListener("mousemove", move)
    el.addEventListener("mouseleave", reset)
    return () => {
      el.removeEventListener("mousemove", move)
      el.removeEventListener("mouseleave", reset)
    }
  }, [strength])
  return ref
}
