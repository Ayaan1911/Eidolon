import assert from "node:assert/strict"
import test from "node:test"
import { repoToFindings } from "./findings.js"

test("partial scans retain actionable findings alongside the warning", () => {
  const result = repoToFindings("user", { incomplete: true, incomplete_reason: "quota", repos_scanned: 1,
    total_findings: 1, results: [{ repo: "user/repo", findings: [{ id: "stable-id", type: "API key", file: "config", line: 1, severity: "High" }] }] })
  assert.equal(result.length, 2)
  assert.equal(result[0].empty, true)
  assert.equal(result[1].raw.id, "stable-id")
  assert.equal(result[1].raw.repo, "user/repo")
})

test("skipped lines and interrupted empty scans never claim to be clean", () => {
  const base = { repos_scanned: 1, total_findings: 0, results: [] }
  assert.match(repoToFindings("user", { ...base, incomplete: true, incomplete_reason: "quota" })[0].summary, /interrupted/)
  assert.match(repoToFindings("user", { ...base, incomplete: false, skipped_long_lines: 2 })[0].summary, /skipped 2/)
})

test("interrupted scans report skipped lines and keep their findings", () => {
  const result = repoToFindings("user", { incomplete: true, incomplete_reason: "quota", skipped_long_lines: 2,
    repos_scanned: 1, total_findings: 1, results: [{ repo: "user/repo", findings: [{ id: "stable-id", type: "API key", file: "config", line: 1, severity: "High" }] }] })
  assert.match(result[0].summary, /2 long lines were skipped/)
  assert.equal(result[1].raw.id, "stable-id")
})
