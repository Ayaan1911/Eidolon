// Admin session token in localStorage. The server is the authority on whether
// a token is valid; the expiry parsed here only lets the UI drop an obviously
// dead token without a round trip.
const KEY = "eidolon:admin-token"

function expiryMs(token) {
  const match = /^eidolon_admin_(\d+)\./.exec(token)
  return match ? Number(match[1]) * 1000 : 0
}

export function getAdminToken() {
  try {
    const token = localStorage.getItem(KEY)
    if (token && expiryMs(token) > Date.now()) return token
    if (token) localStorage.removeItem(KEY)
  } catch {
    // Storage unavailable (private mode, etc.) — treated as logged out.
  }
  return null
}

export function setAdminToken(token) {
  try {
    localStorage.setItem(KEY, token)
  } catch {
    // Storage unavailable — login won't persist past this page load.
  }
}

export function clearAdminToken() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // Nothing to clear.
  }
}
