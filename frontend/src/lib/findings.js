function breachYear(dateStr) {
  const year = dateStr?.match(/\d{4}/)?.[0]
  return year ? ` (${year})` : ""
}

export function emailToFindings(email, result) {
  if (result.total_breaches === 0) {
    return [
      {
        type: "breach",
        // Informational only - Dossier renders this without Trap/Decoy actions,
        // since there's no real finding here to attach either to.
        empty: true,
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
  const found = result.results.flatMap((repo) =>
    repo.findings.map((f) => ({
      type: "secret",
      summary: `A ${f.type} was found exposed in ${repo.repo} at ${f.file}, line ${f.line}.`,
      severity: f.severity,
      // repo isn't on the backend's per-finding object; the deploy request needs it.
      raw: { ...f, repo: repo.repo },
    }))
  )
  // An interrupted scan (almost always GitHub's unauthenticated rate limit) must say so,
  // not read as "checked and clean" - the two look identical once collapsed to 0 findings.
  if (result.incomplete || result.skipped_long_lines > 0) {
    return [
      {
        type: "secret",
        empty: true,
        summary: result.incomplete ? `Repo scan for @${username} was interrupted after ${result.repos_scanned} repo${
          result.repos_scanned === 1 ? "" : "s"
        } - ${result.incomplete_reason}.${result.skipped_long_lines > 0 ? ` ${result.skipped_long_lines} long lines were skipped.` : ""} Results may be incomplete; try again shortly.`
          : `Repo scan for @${username} skipped ${result.skipped_long_lines} long lines; review them manually.`,
        severity: "None",
        raw: result,
      },
      ...found,
    ]
  }
  if (result.total_findings === 0) {
    return [
      {
        type: "secret",
        // Informational only - Dossier renders this without Trap/Decoy actions,
        // since there's no real finding here to attach either to.
        empty: true,
        summary: `No exposed secrets were found across the last ${result.repos_scanned} scanned repos for @${username}.`,
        severity: "None",
        raw: result,
      },
    ]
  }
  return found
}
