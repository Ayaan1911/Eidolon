const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001"

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

export function createTrap(name) {
  return postJson("/api/traps", { name })
}

export async function getTrapAlerts() {
  const res = await fetch(`${API_BASE}/api/traps/alerts`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return res.json()
}
