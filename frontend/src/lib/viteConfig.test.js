import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import config from "../../vite.config.js"

test("production builds require an HTTPS API origin", () => {
  const original = process.env.VITE_API_BASE
  try {
    for (const value of [" ", "localhost", "http://localhost:8001", "https://api.example.com/path", "https://user:pass@api.example.com"]) {
      process.env.VITE_API_BASE = value
      assert.throws(() => config({ command: "build", mode: "test" }), /HTTPS backend origin/)
    }
    process.env.VITE_API_BASE = "https://api.example.com/"
    assert.ok(config({ command: "build", mode: "test" }).plugins)
  } finally {
    if (original === undefined) delete process.env.VITE_API_BASE
    else process.env.VITE_API_BASE = original
  }
})

test("locked Vite excludes the affected 8.3.0–8.3.6 releases", () => {
  const lock = JSON.parse(readFileSync(new URL("../../package-lock.json", import.meta.url)))
  const [major, minor, patch] = lock.packages["node_modules/vite"].version.split(".").map(Number)
  assert.ok(major > 8 || (major === 8 && (minor > 3 || (minor === 3 && patch >= 7))))
})
