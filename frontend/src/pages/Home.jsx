import { Link } from "react-router-dom"
import Stamp from "../components/Stamp"

// The three Mirror checks — pitch-version copy (builds on each tool's own
// /email, /photo, /repo intro rather than repeating it).
const tools = [
  {
    n: "01",
    to: "/email",
    name: "Email breach check",
    cta: "Check your email",
    copy: "Your address is the first thread anyone pulls. Eidolon runs it against the known breach corpora — the dumps that get traded and reposted for years — and tells you which ones you're already sitting in, and what leaked alongside it. Every match is a password someone, somewhere, has already tried.",
  },
  {
    n: "02",
    to: "/photo",
    name: "Photo metadata check",
    cta: "Read a photo",
    copy: "A photo is rarely just the picture. The file quietly remembers what the image doesn't show — the exact device, the second the shutter fell, and often the precise coordinates where you were standing. Drop one in and Eidolon reads back everything the file can still give away about you.",
  },
  {
    n: "03",
    to: "/repo",
    name: "GitHub secret scan",
    cta: "Scan the repos",
    copy: "Public code carries private mistakes. A key pasted in to make something work at 2am, a token only ever meant for local testing — committed once, and still sitting in the history. Hand Eidolon a username and it walks the account's non-fork repositories looking for exactly that.",
  },
]

function Eyebrow({ children }) {
  return (
    <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-redact mb-4">
      {children}
    </p>
  )
}

const ctaLink =
  "inline-block font-mono text-xs uppercase tracking-wider text-redact border border-redact px-3 py-1.5 hover:bg-redact-soft hover:text-ink transition-colors"

export default function Home() {
  return (
    <div>
      {/* 1 — Hero (unchanged: title, glow, thesis) */}
      <header className="relative pt-6 pb-16">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 h-72 w-[36rem] max-w-full"
          style={{
            background:
              "radial-gradient(closest-side, rgba(224,166,90,0.28), rgba(224,166,90,0.10) 45%, transparent 72%)",
          }}
        />
        <h1 className="relative font-display text-6xl sm:text-7xl text-parchment leading-[0.92] tracking-tight mb-5">
          Your Eidolon
        </h1>
        <p className="relative text-base text-parchment-dim max-w-md leading-relaxed">
          See what can be discovered about you without your knowing — before
          someone else assembles it first. Run any check; the findings build up
          into a running dossier.
        </p>
      </header>

      {/* 2 — The Mirror */}
      <section className="py-20 sm:py-28 border-t border-line/15">
        <Eyebrow>The Mirror</Eyebrow>
        <h2 className="font-display text-4xl sm:text-5xl text-parchment tracking-tight leading-[1.05] mb-6 max-w-xl">
          You can't defend what you don't know is exposed.
        </h2>
        <p className="text-parchment-dim leading-relaxed max-w-xl mb-16">
          Most of what a stranger could learn about you isn't hidden — it's just
          scattered. Sitting in an old breach, buried in a photo's metadata,
          committed to a repo you forgot was public. Eidolon holds up the mirror:
          it goes looking the way someone else would, and shows you what comes
          back.
        </p>

        <div className="flex flex-col gap-14">
          {tools.map((t) => (
            <div key={t.to} className="border-l-2 border-redact/50 pl-5 sm:pl-6">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-parchment-dim mb-2">
                {t.n} — Mirror
              </p>
              <h3 className="font-display text-2xl sm:text-3xl text-parchment mb-3">
                {t.name}
              </h3>
              <p className="text-parchment-dim leading-relaxed max-w-lg mb-5">
                {t.copy}
              </p>
              <Link to={t.to} className={ctaLink}>
                {t.cta} →
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* 3 — The Dossier (right-weighted, faint redaction bars behind) */}
      <section className="relative py-20 sm:py-28 border-t border-line/15 overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 flex flex-col justify-center items-end gap-3 opacity-[0.07]"
        >
          <span className="h-8 w-[72%] bg-parchment-dim" />
          <span className="h-8 w-[44%] bg-parchment-dim" />
          <span className="h-8 w-[61%] bg-parchment-dim" />
          <span className="h-8 w-[35%] bg-parchment-dim" />
          <span className="h-8 w-[53%] bg-parchment-dim" />
        </div>
        <div className="relative ml-auto max-w-xl text-right">
          <Eyebrow>The Dossier</Eyebrow>
          <h2 className="font-display text-4xl sm:text-5xl text-parchment tracking-tight leading-[1.05] mb-6">
            Three checks. One case file.
          </h2>
          <p className="text-parchment-dim leading-relaxed mb-6">
            Eidolon never hands you three disconnected reports. Every finding —
            the breach, the location, the leaked key — is stamped and filed onto
            the same page, because no single one is the story. The story is what
            they add up to. This is the file someone else would be assembling on
            you; here, it's yours to read first.
          </p>
          <Link to="/dossier" className={ctaLink}>
            Open the dossier →
          </Link>
        </div>
      </section>

      {/* 4 — The Trap (left, large faint DEPLOYED stamp behind) */}
      <section className="relative py-20 sm:py-28 border-t border-line/15 overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute top-8 right-0 origin-top-right scale-[2.8] opacity-[0.16] hidden sm:block"
        >
          <Stamp label="DEPLOYED" tone="deployed" />
        </div>
        <div className="relative max-w-xl">
          <Eyebrow>The Trap</Eyebrow>
          <h2 className="font-display text-4xl sm:text-5xl text-parchment tracking-tight leading-[1.05] mb-6">
            Stop watching the mirror. Watch who steps up to it.
          </h2>
          <p className="text-parchment-dim leading-relaxed max-w-lg mb-6">
            Knowing where you're exposed is only half of it. Once a weak point is
            on the page, you can leave something there — a canary that looks like
            a working credential, a link worth snooping — that quietly logs
            whoever takes the bait. Deploy one straight from a finding and it
            carries that finding's context with it: when the trap trips, you know
            exactly which exposure they were following.
          </p>
          <Link to="/trap-lab" className={ctaLink}>
            Set a trap →
          </Link>
        </div>
      </section>

      {/* 5 — Closing */}
      <section className="py-24 sm:py-32 border-t border-line/15 text-center">
        <p className="font-display text-3xl sm:text-4xl text-parchment leading-snug max-w-xl mx-auto mb-9">
          The most honest picture of you is the one you never meant to leave.
          Better to find it first.
        </p>
        <Link
          to="/email"
          className="inline-block bg-redact text-parchment font-mono text-sm uppercase tracking-[0.15em] px-6 py-3 hover:opacity-90 transition-opacity"
        >
          Start with your email →
        </Link>
      </section>
    </div>
  )
}
