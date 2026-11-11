import assert from "node:assert/strict"
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
