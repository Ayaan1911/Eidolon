// "Example Broadband / Example Networks Ltd": ISP and org, deduped, skipping blanks and
// the backend's "Unknown" placeholder (a failed lookup).
function network(alert) {
  return [alert.isp, alert.org]
    .filter((part, i, all) => part && part !== "Unknown" && all.indexOf(part) === i)
    .join(" / ")
}

// One signal-stream entry. Everything here is untrusted visitor input (referrer,
// email), so it is rendered as plain text only, never as a link or markup.
export default function SignalRow({ alert, time }) {
  const net = network(alert)
  const loginAttempt = alert.password_attempted != null // null on a plain page load

  return (
    <li className="flex gap-3 px-3 py-1.5 border-b border-hairline last:border-0">
      <span className="text-fg shrink-0">{time}</span>
      <div className="min-w-0 flex-1">
        <p className="text-fg-dim truncate">
          {alert.location}
          {net && ` · ${net}`}
        </p>
        <p className="text-fg-faint truncate">
          {alert.browser}/{alert.os} · {alert.ip} · trap {alert.trap_id}
        </p>
        {alert.referer && <p className="text-fg-faint truncate">via {alert.referer}</p>}
        {loginAttempt && (
          <p className="text-fg truncate">
            login attempt · {alert.email || "(no email)"} ·{" "}
            {alert.password_attempted
              ? `password entered (${alert.password_length} chars)`
              : "password left blank"}
          </p>
        )}
      </div>
    </li>
  )
}
