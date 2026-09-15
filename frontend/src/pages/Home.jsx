import Stamp from "../components/Stamp"
import Eyebrow from "../components/Eyebrow"
import Reveal from "../components/Reveal"
import Cta from "../components/Cta"

// Emphasis word inside a Special Elite headline — a body-font italic break so
// each headline has an internal focal point (type contrast, not color).
function Em({ children }) {
  return (
    <span className="font-sans italic font-medium tracking-normal">{children}</span>
  )
}

// The three Mirror checks — pitch-version copy.
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

const headline =
  "font-display text-4xl sm:text-5xl text-parchment tracking-tight leading-[1.05]"
// Two-column editorial longform at >=768px, single column below.
const longform = "text-parchment-dim leading-relaxed md:columns-2 md:gap-10"

export default function Home() {
  return (
    <div>
      {/* 1 — Hero */}
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
      <Reveal>
        <section className="py-20 sm:py-28 border-t border-line/15">
          <Eyebrow className="mb-4">The Mirror</Eyebrow>
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

          <div className="flex flex-col gap-14">
            {tools.map((t, i) => (
              <Reveal key={t.to} delay={i * 80}>
                <div className="border-l-2 border-redact pl-5 sm:pl-6">
                  <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-parchment-dim mb-2">
                    {t.n} — Mirror
                  </p>
                  <h3 className="font-display text-2xl sm:text-3xl text-parchment mb-3">
                    {t.name}
                  </h3>
                  <p className="text-parchment-dim leading-relaxed max-w-lg mb-5">
                    {t.copy}
                  </p>
                  <Cta to={t.to}>{t.cta} →</Cta>
                </div>
              </Reveal>
            ))}
          </div>
        </section>
      </Reveal>

      {/* 3 — The Dossier (kicker right-aligned, faint redaction bars behind) */}
      <Reveal>
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
          <div className="relative">
            <div className="flex justify-end">
              <Eyebrow className="mb-4">The Dossier</Eyebrow>
            </div>
            <h2 className={`${headline} mb-6 text-right`}>
              Three checks. <Em>One</Em> case file.
            </h2>
            <p className={longform}>
              Eidolon never hands you three disconnected reports. Every finding —
              the breach, the location, the leaked key — is stamped and filed onto
              the same page, because no single one is the story. The story is what
              they add up to. This is the file someone else would be assembling on
              you; here, it's yours to read first, while there's still time to do
              something about it.
            </p>
            <div className="mt-8 flex justify-end">
              <Cta to="/dossier">Open the dossier →</Cta>
            </div>
          </div>
        </section>
      </Reveal>

      {/* 4 — The Trap (large faint DEPLOYED stamp behind) */}
      <Reveal>
        <section className="relative py-20 sm:py-28 border-t border-line/15 overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute top-8 right-0 origin-top-right scale-[2.8] opacity-[0.16] hidden sm:block"
          >
            <Stamp label="DEPLOYED" tone="deployed" />
          </div>
          <div className="relative">
            <Eyebrow className="mb-4">The Trap</Eyebrow>
            <h2 className={`${headline} mb-6 max-w-2xl`}>
              Stop watching the mirror. Watch <Em>who</Em> steps up to it.
            </h2>
            <p className={`${longform} mb-8`}>
              Knowing where you're exposed is only half of it. Once a weak point is
              on the page, you can leave something there — a canary that looks like
              a working credential, a link worth snooping — that quietly logs
              whoever takes the bait. Deploy one straight from a finding and it
              carries that finding's context with it: when the trap trips, you know
              exactly which exposure they were following, and who followed it.
            </p>
            <Cta to="/trap-lab">Set a trap →</Cta>
          </div>
        </section>
      </Reveal>

      {/* 5 — Closing */}
      <Reveal>
        <section className="py-24 sm:py-32 border-t border-line/15 text-center">
          <p className="font-display text-3xl sm:text-4xl text-parchment leading-snug max-w-xl mx-auto mb-9">
            The most honest picture of you is the one you never meant to leave.
            Better to find it <Em>first</Em>.
          </p>
          <Cta to="/email" variant="solid" className="px-6 py-3 text-sm">
            Start with your email →
          </Cta>
        </section>
      </Reveal>
    </div>
  )
}
