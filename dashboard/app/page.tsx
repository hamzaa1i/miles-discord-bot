import Link from 'next/link';

import BotStatusCard from '@/components/BotStatusCard';
import { Icon } from '@/components/icons';

const FEATURES = [
  { icon: 'heart', title: 'welcome cards', desc: 'greet every soul with embeds, colors and live previews.' },
  { icon: 'star', title: 'leveling', desc: 'tune xp rates, level-up messages and role rewards.' },
  { icon: 'helpCircle', title: 'qotd', desc: 'schedule the daily question, curate a custom queue.' },
  { icon: 'shield', title: 'ai automod', desc: 'the watchful gaze — severity, timeouts, alerts.' },
  { icon: 'gift', title: 'giveaways', desc: 'watch entries arrive in realtime, end them early.' },
  { icon: 'barChart', title: 'statistics', desc: 'commands per day, top commands, leaderboards.' },
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

          {/* live bot status — replaces the old raw-json "bot status" link */}
          <BotStatusCard className="mt-8" />

          <div className="mt-8">
            <Link href="/login" className="veloura-button-primary px-8 text-base">
              <Icon name="logout" size={17} />
              login with discord
            </Link>
          </div>
          <p className="mt-4 text-xs text-veloura-muted/70">
            only servers where you have <span className="text-veloura-pink">manage server</span> appear
          </p>
        </section>

        {/* feature grid */}
        <section className="grid gap-4 pb-16 sm:grid-cols-2 lg:grid-cols-3" aria-label="dashboard features">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              style={{ animationDelay: `${120 + i * 80}ms` }}
              className="group animate-rise veloura-card relative p-5 transition-all duration-300 hover:-translate-y-1 hover:border-veloura-pink/40 hover:shadow-glow"
            >
              {/* soft gradient wash on hover */}
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 rounded-card bg-gradient-to-br from-veloura-pink/0 via-veloura-lavender/0 to-veloura-pink/0 opacity-0 transition-opacity duration-300 group-hover:from-veloura-pink/[0.06] group-hover:via-veloura-lavender/[0.04] group-hover:to-transparent group-hover:opacity-100"
              />
              <div className="relative">
                <div
                  aria-hidden
                  className="mb-3 flex h-10 w-10 items-center justify-center rounded-[12px] bg-veloura-card-hover text-veloura-pink transition-all duration-300 group-hover:scale-110 group-hover:border group-hover:border-veloura-pink/30 group-hover:shadow-glow"
                >
                  <Icon name={f.icon} size={19} />
                </div>
                <h2 className="font-heading text-lg text-veloura-text transition-colors duration-300 group-hover:text-veloura-lavender">
                  {f.title}
                </h2>
                <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">{f.desc}</p>
              </div>
            </div>
          ))}
        </section>

        <footer className="mt-auto border-t border-veloura-border/60 py-8 text-center text-sm text-veloura-muted/70">
          <span className="twinkle" aria-hidden>
            ✦
          </span>{' '}
          built by volc · wrapped in veloura ·{' '}
          <span className="twinkle" aria-hidden>
            ✧
          </span>
        </footer>
      </main>
    </div>
  );
}
