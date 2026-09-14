function breachYear(dateStr) {
  const year = dateStr?.match(/\d{4}/)?.[0]
  return year ? ` (${year})` : ""
}

export function emailToFindings(email, result) {
  if (result.total_breaches === 0) {
    return [
      {
        type: "breach",
        summary: `No known breaches were found for ${email}.`,
        severity: "None",
        raw: result,
      },
    ]
  }
  return result.breaches.map((breach) => ({
    type: "breach",
    summary: `Your email appeared in the ${breach.name} breach${breachYear(
      breach.date
    )} — ${breach.data_exposed.join(", ")} were exposed.`,
    severity: breach.severity,
    raw: breach,
  }))
}

export function photoToFindings(result, formatCapturedAt) {
  if (result.has_location) {
    const when = result.captured_at ? ` on ${formatCapturedAt(result.captured_at)}` : ""
    return [
      {
        type: "photo",
        summary: `This photo places you at ${result.latitude.toFixed(5)}, ${result.longitude.toFixed(
          5
        )}${when}.`,
        severity: "High",
        raw: result,
      },
    ]
  }
  if (result.device || result.captured_at) {
    const parts = []
    if (result.device) parts.push(`was taken on a ${result.device}`)
    if (result.captured_at) parts.push(`on ${formatCapturedAt(result.captured_at)}`)
    return [
      {
        type: "photo",
        summary: `A photo you checked carried no GPS data, but metadata shows it ${parts.join(" ")}.`,
        severity: "Low",
        raw: result,
      },
    ]
  }
  return [
    {
      type: "photo",
      summary: "A photo you checked carried no location or device metadata.",
      severity: "None",
      raw: result,
    },
  ]
}

export function repoToFindings(username, result) {
  if (result.total_findings === 0) {
    return [
      {
        type: "secret",
        summary: `No exposed secrets were found across the last ${result.repos_scanned} scanned repos for @${username}.`,
        severity: "None",
        raw: result,
      },
    ]
  }
  return result.results.flatMap((repo) =>
    repo.findings.map((f) => ({
      type: "secret",
      summary: `A ${f.type} was found exposed in ${username}/${repo.repo} at ${f.file}, line ${f.line}.`,
      severity: f.severity,
      raw: f,
    }))
  )
}
