import test from "node:test"
import assert from "node:assert/strict"
import { pwnedCount, sha1Hex } from "./pwned.js"

// SHA-1("password") = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8 (the standard worked example)
const SUFFIX = "1E4C9B93F3F0682250B6CF8331B7EE68FD8"

function fakeFetch(body, ok = true) {
  const calls = []
  const fn = async (url, init) => {
    calls.push({ url, init })
    return { ok, text: async () => body }
  }
  fn.calls = calls
  return fn
}

test("sha1Hex matches the known digest", async () => {
  assert.equal(await sha1Hex("password"), "5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8")
})

test("only the 5-character prefix is sent, with padding on", async () => {
  const pw = "correct-horse-7Q"
  const hash = await sha1Hex(pw)
  const f = fakeFetch(`${hash.slice(5)}:42
AAAA:1`)
  assert.equal(await pwnedCount(pw, f), 42)
  assert.equal(f.calls.length, 1)
  assert.equal(f.calls[0].url, "https://api.pwnedpasswords.com/range/" + hash.slice(0, 5))
  assert.equal(f.calls[0].init.headers["Add-Padding"], "true")
  const sent = JSON.stringify(f.calls)
  assert.ok(!sent.includes(hash.slice(5)), "the hash suffix must stay local")
  assert.ok(!sent.includes(pw), "the password must stay local")
})

test("padding rows (count 0) and a missing suffix both mean not found", async () => {
  assert.equal(await pwnedCount("password", fakeFetch(`${SUFFIX}:0\nBBBB:3`)), 0)
  assert.equal(await pwnedCount("password", fakeFetch("BBBB:3")), 0)
})

test("a failed lookup throws a generic message", async () => {
  await assert.rejects(pwnedCount("password", fakeFetch("", false)), /did not answer/)
  const boom = async () => { throw new TypeError("secret detail") }
  await assert.rejects(pwnedCount("password", boom), (e) => !e.message.includes("secret detail"))
})
