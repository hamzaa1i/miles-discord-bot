import Link from 'next/link';

const FEATURES = [
  { icon: '♡', title: 'welcome cards', desc: 'greet every soul with embeds, colors and live previews.' },
  { icon: '✩', title: 'leveling', desc: 'tune xp rates, level-up messages and role rewards.' },
  { icon: '❓', title: 'qotd', desc: 'schedule the daily question, curate a custom queue.' },
  { icon: '👁', title: 'ai automod', desc: 'the watchful gaze — severity, timeouts, alerts.' },
  { icon: '🎁', title: 'giveaways', desc: 'watch entries arrive in realtime, end them early.' },
  { icon: '📈', title: 'statistics', desc: 'commands per day, top commands, leaderboards.' },
];

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* ambient glow */}
      <div className="pointer-events-none absolute -top-32 left-1/2 h-[420px] w-[680px] -translate-x-1/2 rounded-full bg-veloura-pink/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[300px] w-[420px] rounded-full bg-veloura-lavender/5 blur-3xl" />

      <main className="relative mx-auto flex max-w-5xl flex-col px-6">
        {/* hero */}
        <section className="flex flex-col items-center pb-14 pt-24 text-center animate-fade-in">
          <img
            src="/aurelia-logo.png"
            alt="aurelia logo — a soft pink four-pointed star"
            width={112}
            height={112}
            className="mb-8 animate-float-slow"
          />
          <h1 className="font-heading text-5xl font-medium tracking-wide text-veloura-text sm:text-6xl">
            aurelia
          </h1>
          <p className="mt-4 max-w-xl text-lg leading-relaxed text-veloura-muted">
            the veloura command center — configure every feature of your
            discord server through the browser, no slash commands required.
          </p>
          <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
            <Link href="/login" className="veloura-button-primary px-8 text-base">
              ✦ login with discord
            </Link>
            <a
              href="https://miles-discord-bot.onrender.com/health"
              target="_blank"
              rel="noreferrer"
              className="veloura-button-ghost px-6 text-base"
            >
              bot status
            </a>
          </div>
          <p className="mt-4 text-xs text-veloura-muted/70">
            only servers where you have <span className="text-veloura-pink">manage server</span> appear
          </p>
        </section>

        {/* feature grid */}
        <section className="grid gap-4 pb-16 sm:grid-cols-2 lg:grid-cols-3" aria-label="dashboard features">
          {FEATURES.map((f) => (
            <div key={f.title} className="veloura-card p-5 transition hover:border-veloura-pink/40 hover:shadow-glow">
              <div className="mb-3 text-2xl" aria-hidden>
                {f.icon}
              </div>
              <h2 className="font-heading text-lg text-veloura-text">{f.title}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">{f.desc}</p>
            </div>
          ))}
        </section>

        <footer className="mt-auto border-t border-veloura-border/60 py-8 text-center text-sm text-veloura-muted/70">
          <span className="twinkle">✦</span> built by volc · wrapped in veloura ·{' '}
          <span className="twinkle">✧</span>
        </footer>
      </main>
    </div>
  );
}
