// Breached-password check using k-anonymity (Have I Been Pwned "range" API).
// Only the first 5 hex characters of the password's SHA-1 leave the browser. The
// password and the full hash are never sent anywhere (not even to the Eidolon server).
const RANGE_URL = "https://api.pwnedpasswords.com/range/"

export async function sha1Hex(text) {
  const bytes = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest("SHA-1", bytes)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").toUpperCase()
}

// Returns how many times the password appears in known breaches (0 = not found).
export async function pwnedCount(password, fetchImpl = fetch) {
  const hash = await sha1Hex(password)
  const prefix = hash.slice(0, 5)
  const suffix = hash.slice(5)
  let res
  try {
    // Add-Padding makes every answer a similar size, so the response length leaks nothing.
    res = await fetchImpl(RANGE_URL + prefix, { headers: { "Add-Padding": "true" } })
  } catch {
    throw new Error("Could not reach the breached-password service. Try again later.")
  }
  if (!res.ok) throw new Error("The breached-password service did not answer. Try again later.")
  for (const line of (await res.text()).split("\n")) {
    const [candidate, count] = line.trim().split(":")
    // Padding rows have a count of 0, so they never count as a match.
    if (candidate === suffix) return Number(count) || 0
  }
  return 0
}
