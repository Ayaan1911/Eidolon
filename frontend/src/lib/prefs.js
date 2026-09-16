// Tiny localStorage-backed preferences — reduce-motion override and the
// dossier's default filter. Read on the /system settings page and applied
// wherever the corresponding UI needs the stored value.
const KEY_MOTION = "eidolon:reduce-motion"
const KEY_FILTER = "eidolon:dossier-filter"

export function getReduceMotion() {
  try {
    return localStorage.getItem(KEY_MOTION) === "1"
  } catch {
    return false
  }
}

export function setReduceMotion(on) {
  try {
    localStorage.setItem(KEY_MOTION, on ? "1" : "0")
  } catch {
    // Storage unavailable (private mode, etc.) — class still toggles for this tab.
  }
  document.documentElement.classList.toggle("reduce-motion", on)
}

export function getDefaultDossierFilter() {
  try {
    return localStorage.getItem(KEY_FILTER) || "all"
  } catch {
    return "all"
  }
}

export function setDefaultDossierFilter(key) {
  try {
    localStorage.setItem(KEY_FILTER, key)
  } catch {
    // Storage unavailable — selection just won't persist across reloads.
  }
}
