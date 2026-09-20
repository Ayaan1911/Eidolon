// Dev falls back to the local backend; a production build must set VITE_API_BASE
// (Vercel env var) or requests would silently target the visitor's own localhost.
const configuredBase = import.meta.env.VITE_API_BASE
if (!configuredBase && !import.meta.env.DEV) {
  throw new Error("VITE_API_BASE is not set - point it at the deployed backend URL.")
}
// Trailing slashes stripped so "https://host/" doesn't yield "https://host//api/...".
const API_BASE = (configuredBase || "http://localhost:8001").replace(/\/+$/, "")

async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export function checkEmailExposure(email) {
  return postJson("/api/exposure/email", { email })
}

export function checkPasswordStrength(password) {
  return postJson("/api/exposure/password", { password })
}

export function scanGithubRepos(username) {
  return postJson("/api/exposure/repos", { username })
}

export async function checkPhotoMetadata(file) {
  const formData = new FormData()
  formData.append("file", file)
  const res = await fetch(`${API_BASE}/api/exposure/photo`, {
    method: "POST",
    body: formData,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export function createTrap({ name, source_type, context }) {
  return postJson("/api/traps", { name, source_type, context })
}

export async function deployDecoy(findingId) {
  const res = await fetch(`${API_BASE}/api/findings/${findingId}/deploy-decoy`, { method: "POST" })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export async function getTrapAlerts() {
  const res = await fetch(`${API_BASE}/api/traps/alerts`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return res.json()
}
