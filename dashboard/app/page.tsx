import Link from 'next/link';

import { Icon } from '@/components/icons';
import { CommandGrid } from '@/components/site/CommandGrid';
import { Faq } from '@/components/site/Faq';
import { FeatureShowcase } from '@/components/site/FeatureShowcase';
import { LandingStatsBar } from '@/components/site/LandingStatsBar';
import { ShareButtons } from '@/components/site/ShareButtons';
import { SiteFooter } from '@/components/site/SiteFooter';
import { SiteHeader } from '@/components/site/SiteHeader';
import { botInviteUrl, siteUrl, SUPPORT_SERVER_URL } from '@/lib/marketing';
import { pageMetadata, softwareApplicationJsonLd } from '@/lib/seo';

/**
 * app/page.tsx — PHASE M PART 1 — the public marketing landing page.
 *
 * The dashboard moved to /login + /servers (middleware untouched);
 * "/" is now the shop window: hero, live stats, six feature
 * showcases, social proof, command grid, pricing, faq and footer.
 * Server-rendered except the live stats bar + share buttons.
 */

export const metadata = pageMetadata({
  title: 'aurelia — soft, elegant discord bot for veloura communities',
  description:
    'ai chat, aesthetic moderation, community engagement. free forever. built with love.',
  path: '/',
});

const INVITE = botInviteUrl();

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      {/* ── ambient animated gradient (soft pink → lavender → navy) ── */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[720px] bg-gradient-drift"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[480px] w-[820px] -translate-x-1/2 rounded-full bg-veloura-pink/10 blur-3xl"
      />

      <SiteHeader />

      <main className="relative">
        {/* ══ 1 · hero ════════════════════════════════════════════════ */}
        <section className="mx-auto flex max-w-6xl flex-col items-center px-6 pb-16 pt-20 text-center sm:pt-24">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/aurelia-logo.png"
            alt="aurelia logo — a soft pink four-pointed star on a deep navy night"
            width={128}
            height={128}
            className="animate-float-slow transition-transform duration-500 hover:scale-110 hover:rotate-6"
          />
          <h1 className="font-heading mt-8 text-4xl font-medium tracking-wide text-veloura-text sm:text-5xl">
            the soft, elegant discord bot{' '}
            <span className="twinkle text-veloura-pink" aria-hidden>
              ✦
            </span>
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-veloura-muted">
            aesthetic moderation, ai chat, and community features for your
            veloura-vibe server — she remembers you, greets every soul and
            keeps the vibes alive.
          </p>

          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
            {INVITE ? (
              <a
                href={INVITE}
                target="_blank"
                rel="noopener noreferrer"
                className="veloura-button-primary px-8 text-base"
                aria-label="add aurelia to your discord server (opens discord's authorization page)"
              >
                <Icon name="plus" size={17} />
                add to discord
                <span aria-hidden>✦</span>
              </a>
            ) : (
              <Link href="/login" className="veloura-button-primary px-8 text-base">
                <Icon name="logout" size={17} />
                login with discord
              </Link>
            )}
            <Link href="/login" className="veloura-button-ghost px-8 text-base">
              <Icon name="settings" size={16} />
              login to dashboard
            </Link>
          </div>

          {/* ══ 2 · live stats bar (auto-refresh 60s) ═══════════════ */}
          <LandingStatsBar className="mt-12" />
        </section>

        {/* ══ 3 · feature showcase ═══════════════════════════════════ */}
        <div className="py-16">
          <FeatureShowcase />
        </div>

        {/* ══ 4 · social proof ═══════════════════════════════════════ */}
        <section aria-label="what communities say" className="py-16">
          <div className="mx-auto max-w-6xl px-6">
            <header className="mb-10 text-center">
              <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">
                word of mouth
              </p>
              <h2 className="font-heading mt-2 text-3xl text-veloura-text sm:text-4xl">
                trusted by soft communities
              </h2>
            </header>

            {/* placeholder testimonials — filled in as they arrive */}
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                {
                  quote:
                    'the welcome cards alone made our server feel like a different place. she just… fits ♡',
                  who: 'server owner · aesthetic community',
                },
                {
                  quote:
                    'setup took one command. the dashboard is prettier than most premium bots we pay for.',
                  who: 'admin · 12k-member gaming server',
                },
                {
                  quote:
                    'ai chat that actually remembers our inside jokes, and moderation that stays gentle. rare combo.',
                  who: 'moderator · study lounge',
                },
              ].map((t) => (
                <figure key={t.who} className="veloura-card p-5">
                  <blockquote className="text-sm leading-relaxed text-veloura-text">
                    “{t.quote}”
                  </blockquote>
                  <figcaption className="mt-3 text-xs text-veloura-muted/80">
                    {t.who}
                  </figcaption>
                </figure>
              ))}
            </div>

            <p className="mt-6 text-center text-xs text-veloura-muted/70">
              * placeholder quotes — real ones arrive as communities opt in ✧
            </p>

            {/* growth ticker */}
            <div className="veloura-card mt-8 flex flex-col items-center justify-center gap-2 px-6 py-5 text-center">
              <p className="font-heading text-lg text-veloura-text">
                growing softly, one server at a time
              </p>
              <p className="text-xs text-veloura-muted">
                want your community featured here?{' '}
                {SUPPORT_SERVER_URL ? (
                  <a
                    href={SUPPORT_SERVER_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2"
                  >
                    tell us in the support server
                  </a>
                ) : (
                  <span>opt in via the support server (soon)</span>
                )}
              </p>
            </div>
          </div>
        </section>

        {/* ══ 5 · commands preview ═══════════════════════════════════ */}
        <div className="py-16">
          <CommandGrid />
        </div>

        {/* ══ 6 · pricing ════════════════════════════════════════════ */}
        <section aria-label="pricing" className="py-16">
          <div className="mx-auto max-w-3xl px-6">
            <div className="veloura-card relative overflow-hidden p-8 text-center sm:p-10">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-veloura-pink/50 to-transparent"
              />
              <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">
                pricing
              </p>
              <h2 className="font-heading mt-3 text-3xl text-veloura-text">
                aurelia is 100% free, forever{' '}
                <span className="twinkle text-veloura-pink" aria-hidden>
                  ✦
                </span>
              </h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-veloura-muted">
                no paywalls, no premium tiers, no ads, no locked features.
                every command, every module, every dashboard page — yours.
              </p>
              <ul className="mx-auto mt-6 grid max-w-sm gap-2 text-left">
                {[
                  '167 commands, all free',
                  'full dashboard, all free',
                  'ai chat & memory, all free',
                  'self-hosting? MIT licensed, also free',
                ].map((line) => (
                  <li key={line} className="flex items-center gap-2 text-sm text-veloura-muted">
                    <Icon name="check" size={14} className="text-veloura-success" />
                    {line}
                  </li>
                ))}
              </ul>
              <p className="mt-6 text-xs text-veloura-muted/80">
                hosted with love by{' '}
                <span className="text-veloura-lavender">@volc</span> · enjoy
                her? support with a coffee{' '}
                <a
                  href="https://ko-fi.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2"
                  aria-label="support aurelia's hosting with a coffee (opens ko-fi)"
                >
                  ☕
                </a>
              </p>
            </div>
          </div>
        </section>

        {/* ══ 7 · faq ════════════════════════════════════════════════ */}
        <div className="py-16">
          <Faq />
        </div>

        {/* ══ 8 · share + footer ═════════════════════════════════════ */}
        <section aria-label="share aurelia" className="pb-12 pt-4">
          <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-6">
            <p className="text-xs uppercase tracking-[0.2em] text-veloura-muted/70">
              know a server that needs her?
            </p>
            <ShareButtons
              url={siteUrl()}
              text="i just discovered aurelia — the softest discord bot ✦ add it to your server:"
            />
          </div>
        </section>
      </main>

      <SiteFooter />

      {/* PHASE M PART 9 — JSON-LD structured data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: softwareApplicationJsonLd(INVITE),
        }}
      />
    </div>
  );
}
