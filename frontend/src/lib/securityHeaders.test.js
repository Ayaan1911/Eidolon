import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

test("deployed headers block injected scripts and framing while allowing the app's resources", () => {
  const config = JSON.parse(readFileSync(new URL("../../vercel.json", import.meta.url)))
  assert.ok(config.rewrites.some((rule) => rule.destination === "/index.html"))
  const rule = config.headers.find((entry) => entry.source === "/(.*)")
  const headers = Object.fromEntries(rule.headers.map(({ key, value }) => [key.toLowerCase(), value]))
  assert.equal(headers["x-content-type-options"], "nosniff")
  assert.equal(headers["x-frame-options"], "DENY")
  assert.equal(headers["referrer-policy"], "no-referrer")
  assert.equal(headers["permissions-policy"], "camera=(), microphone=(), geolocation=()")
  assert.equal(headers["strict-transport-security"], "max-age=31536000")
  const directives = Object.fromEntries(headers["content-security-policy"].split(";").map((entry) => {
    const [name, ...sources] = entry.trim().split(/\s+/)
    return [name, sources]
  }))
  assert.deepEqual(directives["script-src"], ["'self'"])
  assert.deepEqual(directives["frame-ancestors"], ["'none'"])
  assert.deepEqual(directives["object-src"], ["'none'"])
  assert.deepEqual(directives["connect-src"], [
    "'self'", "https://eidolon-2515.onrender.com", "https://api.pwnedpasswords.com",
  ])
  assert.ok(directives["style-src"].includes("https://fonts.googleapis.com"))
  assert.ok(directives["style-src"].includes("'unsafe-inline'")) // React uses inline styles.
  assert.ok(directives["font-src"].includes("https://fonts.gstatic.com"))
})
