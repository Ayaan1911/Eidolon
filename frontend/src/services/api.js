import { getAdminToken } from "../lib/adminAuth"

// Dev falls back to the local backend; a production build must set VITE_API_BASE
// (Vercel env var) or requests would silently target the visitor's own localhost.
const configuredBase = import.meta.env.VITE_API_BASE
if (!configuredBase && !import.meta.env.DEV) {
  throw new Error("VITE_API_BASE is not set - point it at the deployed backend URL.")
}
// Trailing slashes stripped so "https://host/" doesn't yield "https://host//api/...".
const API_BASE = (configuredBase || "http://localhost:8001").replace(/\/+$/, "")

// Error carrying the HTTP status, so callers can tell a rejected admin token (401) from other failures.
async function failure(res) {
  const data = await res.json().catch(() => ({}))
  return Object.assign(new Error(data.detail || `Request failed (${res.status})`), { status: res.status })
}

async function postJson(path, body, headers = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw await failure(res)
  return res.json()
}

function adminHeaders() {
  const token = getAdminToken()
  return token ? { Authorization: `Bearer ${token}` } : null
}

export function adminLogin(passphrase) {
  return postJson("/api/admin/login", { passphrase })
}

export function checkEmailExposure(email) {
  return postJson("/api/exposure/email", { email })
}

export function checkPasswordStrength(password) {
  return postJson("/api/exposure/password", { password })
}

export function scanGithubRepos(username) {
  // Sending the admin header (when present) is what lets a finding's response
  // carry trap status - harmless for a logged-out visitor, who has none.
  return postJson("/api/exposure/repos", { username }, adminHeaders() ?? {})
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
  const headers = adminHeaders()
  if (!headers) return Promise.reject(new Error("Deploying traps is admin-only in this public demo."))
  return postJson("/api/traps", { name, source_type, context }, headers)
}

export async function deployDecoy(findingId) {
  const res = await fetch(`${API_BASE}/api/findings/${findingId}/deploy-decoy`, { method: "POST" })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export function deployTrapForFinding(findingId, { repo, file, type }) {
  const headers = adminHeaders()
  if (!headers) return Promise.reject(new Error("Deploying traps is admin-only in this public demo."))
  return postJson(`/api/findings/${findingId}/deploy-trap`, { repo, file, type }, headers)
}

export async function getTrapAlerts() {
  const res = await fetch(`${API_BASE}/api/traps/alerts`, { headers: adminHeaders() ?? {} })
  if (!res.ok) throw await failure(res)
  return res.json()
}
