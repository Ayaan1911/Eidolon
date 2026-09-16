import Eyebrow from "../components/Eyebrow"
import Reveal from "../components/Reveal"
import Cta from "../components/Cta"
import SignalCard from "../components/SignalCard"
import { SystemGrid } from "../lib/systemCards"

// Italic emphasis inside a serif headline (Fraunces italic).
function Em({ children }) {
  return <span className="italic">{children}</span>
}

const tools = [
  {
    n: "01",
    to: "/email",
    name: "Email breach check",
    cta: "Check your email",
    copy: "Your address is the first thread anyone pulls. Eidolon runs it against the known breach corpora — the dumps that get traded and reposted for years — and tells you which ones you're already in, and what leaked alongside it.",
  },
  {
    n: "02",
    to: "/photo",
    name: "Photo metadata check",
    cta: "Read a photo",
    copy: "A photo is rarely just the picture. The file remembers the exact device, the second the shutter fell, and often the precise coordinates where you stood. Drop one in and Eidolon reads back what it still gives away.",
  },
  {
    n: "03",
    to: "/repo",
    name: "GitHub secret scan",
    cta: "Scan the repos",
    copy: "Public code carries private mistakes. A key pasted in at 2am, a token meant only for local testing — committed once, still in the history. Hand Eidolon a username and it walks the non-fork repositories for exactly that.",
  },
]

const headline = "font-serif text-4xl sm:text-5xl text-fg tracking-tight leading-[1.08]"
const longform = "text-fg-dim leading-relaxed md:columns-2 md:gap-10"

export default function Home() {
  return (
    <div>
      {/* 1 — Hero */}
      <header className="pt-10 sm:pt-16 pb-20 sm:pb-28 grid lg:grid-cols-[1.15fr_1fr] gap-12 lg:gap-16 items-center">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-fg-dim border border-hairline px-2 py-1">
              Eidolon
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-fg-faint">
              Build 2026.09
            </span>
          </div>

          <h1 className="font-serif text-6xl sm:text-7xl text-fg tracking-tight leading-[0.98] mb-7">
            Your exposure,
            <br />
            <Em>made legible.</Em>
          </h1>

          <p className="text-base sm:text-lg text-fg-dim max-w-lg leading-relaxed mb-8">
            Eidolon looks you up the way a stranger would — breaches, photo
            metadata, committed secrets — and lays every finding in one quiet
            dossier, each with its reasoning. No scores, no theatrics.
          </p>

          <div className="flex items-center gap-3 mb-10">
            <Cta to="/email" variant="fill">Start with your email</Cta>
            <Cta to="/dossier" variant="ghost">Read the dossier →</Cta>
          </div>

          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-fg-faint">
            One accent · Zero scores · Full reasoning
          </p>
        </div>

        <div className="lg:pl-4">
          <SignalCard />
        </div>
      </header>

      {/* 2 — The Mirror */}
      <Reveal>
        <section className="py-20 sm:py-28 border-t border-hairline">
          <Eyebrow className="mb-5">The Mirror</Eyebrow>
          <h2 className={`${headline} mb-6 max-w-xl`}>
            You can't defend what you don't <Em>know</Em> is exposed.
          </h2>
          <p className={`${longform} mb-16`}>
            Most of what a stranger could learn about you isn't hidden — it's just
            scattered. Sitting in an old breach, buried in a photo's metadata,
            committed to a repo you forgot was public. Eidolon holds up the mirror:
            it goes looking the way someone else would, and shows you exactly what
            comes back — no more guessing at the shape of your own shadow.
          </p>

          <div className="grid gap-12 sm:grid-cols-3">
            {tools.map((t, i) => (
              <Reveal key={t.to} delay={i * 80}>
                <div className="border-t border-hairline pt-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-faint mb-3">
                    {t.n} · Mirror
                  </p>
                  <h3 className="font-serif text-2xl text-fg mb-3">{t.name}</h3>
                  <p className="text-sm text-fg-dim leading-relaxed mb-5">{t.copy}</p>
                  <Cta to={t.to} variant="ghost">{t.cta} →</Cta>
                </div>
              </Reveal>
            ))}
          </div>
        </section>
      </Reveal>

      {/* 3 — The Dossier */}
      <Reveal>
        <section className="py-20 sm:py-28 border-t border-hairline">
          <Eyebrow className="mb-5">The Dossier</Eyebrow>
          <h2 className={`${headline} mb-6 max-w-xl`}>
            Three checks. <Em>One</Em> case file.
          </h2>
          <p className={`${longform} mb-8 max-w-3xl`}>
            Eidolon never hands you three disconnected reports. Every finding — the
            breach, the location, the leaked key — is filed onto the same page,
            because no single one is the story. The story is what they add up to.
            This is the file someone else would be assembling on you; here, it's
            yours to read first, while there's still time to do something about it.
          </p>
          <Cta to="/dossier" variant="ghost">Open the dossier →</Cta>
        </section>
      </Reveal>

      {/* 4 — The Trap */}
      <Reveal>
        <section className="py-20 sm:py-28 border-t border-hairline">
          <Eyebrow className="mb-5">The Trap</Eyebrow>
          <h2 className={`${headline} mb-6 max-w-2xl`}>
            Stop watching the mirror. Watch <Em>who</Em> steps up to it.
          </h2>
          <p className={`${longform} mb-8 max-w-3xl`}>
            Knowing where you're exposed is only half of it. Once a weak point is on
            the page, you can leave something there — a canary that looks like a
            working credential, a link worth snooping — that quietly logs whoever
            takes the bait. Deploy one straight from a finding and it carries that
            finding's context with it: when the trap trips, you know exactly which
            exposure they were following, and who followed it.
          </p>
          <Cta to="/trap-lab" variant="ghost">Set a trap →</Cta>
        </section>
      </Reveal>

      {/* 5 — System / vocabulary */}
      <Reveal>
        <section className="py-20 sm:py-28 border-t border-hairline">
          <Eyebrow className="mb-5">The System</Eyebrow>
          <h2 className={`${headline} mb-6 max-w-xl`}>
            A quiet interface, <Em>on purpose.</Em>
          </h2>
          <p className="text-fg-dim leading-relaxed max-w-2xl mb-12">
            Eidolon's own design language — the surfaces, the one accent, the type,
            the restraint. The same instinct as the product: show what matters,
            nothing louder than it needs to be.
          </p>

          <SystemGrid />

          <div className="mt-8">
            <Cta to="/system" variant="ghost">Open settings & tokens →</Cta>
          </div>
        </section>
      </Reveal>

      {/* 6 — Closing */}
      <Reveal>
        <section className="py-24 sm:py-32 border-t border-hairline text-center">
          <p className="font-serif text-3xl sm:text-4xl text-fg leading-snug max-w-xl mx-auto mb-9">
            The most honest picture of you is the one you never meant to leave.
            Better to find it <Em>first.</Em>
          </p>
          <div className="flex items-center justify-center">
            <Cta to="/email" variant="fill">Start with your email</Cta>
          </div>
        </section>
      </Reveal>
    </div>
  )
}
