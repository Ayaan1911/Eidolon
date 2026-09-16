// Turns a finding into a plain-language "why this matters" rationale — the
// content behind a dossier finding's case-note panel. Narrative, not a score.

function sev(finding) {
  return (finding.severity || "").toLowerCase()
}

export function reasonFor(finding) {
  const s = sev(finding)
  const raw = finding.raw || {}

  if (finding.type === "secret") {
    return {
      verdict: s === "critical" ? "Critical" : s === "high" ? "High" : "Noted",
      notes: [
        `A ${raw.type || "credential"} committed to a public repository is readable by anyone — including the bots that index new commits on GitHub within minutes of a push.`,
        "Deleting the file changes nothing. Git keeps every past version, so the value is still one command away in the history.",
        "The only real fix is to rotate the secret at its source. Until you do, treat it as already in someone else's hands — because it may be.",
      ],
    }
  }

  if (finding.type === "breach") {
    const year = (raw.date || "").match(/\d{4}/)?.[0]
    const exposed = Array.isArray(raw.data_exposed) ? raw.data_exposed.join(", ") : "credentials"
    return {
      verdict: s === "critical" || s === "high" ? "High" : "Noted",
      notes: [
        `${exposed} tied to this address were dumped${year ? ` in ${year}` : ""} and have circulated ever since — copied, traded, and loaded into automated tools.`,
        "Attackers don't guess, they replay. Credential-stuffing software tries leaked email-and-password pairs across hundreds of sites in seconds.",
        "If that password was reused anywhere, assume those accounts are reachable too. Change it everywhere it appeared and turn on two-factor.",
      ],
    }
  }

  if (finding.type === "photo") {
    if (s === "high") {
      return {
        verdict: "High",
        notes: [
          "These coordinates pin you to a specific place at a specific time — not a rough city, a point on a map.",
          "A handful of photos is enough to plot a routine: where you sleep, where you work, when you are not home.",
          "Most platforms never strip this. Remove the EXIF before sharing, and think twice about posting anywhere in real time.",
        ],
      }
    }
    return {
      verdict: "Noted",
      notes: [
        "No coordinates this time — but the file still names the device that took it and the moment it was taken.",
        "Device and timestamp alone can tie a supposedly anonymous photo back to you once they're cross-referenced against anything else.",
      ],
    }
  }

  return {
    verdict: "Clear",
    notes: [
      "Nothing surfaced from this check — but absence of evidence is not proof of safety.",
      "Your footprint shifts every time you sign up, post, or push. Re-run this as it changes.",
    ],
  }
}
