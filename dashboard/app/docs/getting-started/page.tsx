import Link from 'next/link';

import { CodeBlock } from '@/components/docs/CodeBlock';
import { Icon } from '@/components/icons';
import { ShareButtons } from '@/components/site/ShareButtons';
import { botInviteUrl } from '@/lib/marketing';
import { pageMetadata } from '@/lib/seo';

/**
 * app/docs/getting-started/page.tsx — first steps with aurelia:
 * invite → /setup wizard → the three ways to talk to her →
 * where to go next.
 */

export const metadata = pageMetadata({
  title: 'getting started',
  description:
    'add aurelia to your discord server, run the setup wizard, and learn the three ways to talk to her — slash commands, @mentions and prefixes.',
  path: '/docs/getting-started',
});

const STEPS = [
  {
    n: 1,
    title: 'add her to your server',
    body: 'the invite link asks for a curated permission set (moderation, roles, messages — never administrator). you need the manage server permission in the target server.',
  },
  {
    n: 2,
    title: 'run the setup wizard',
    body: 'one command walks you through the essentials: pick features, pick channels, test them. new servers also get a friendly DM version automatically.',
  },
  {
    n: 3,
    title: 'talk to her',
    body: 'slash commands for everything, natural language through @aurelia, or the classic prefix. whichever feels softest.',
  },
];

export default function GettingStarted() {
  const invite = botInviteUrl();

  return (
    <>
      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">getting started</p>
        <h1 className="font-heading mt-2 text-4xl text-veloura-text">from zero to soft ✦</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
          three steps, five minutes, one very polite bot. by the end your
          server greets newcomers, awards xp and has a guardian angel with
          opinions about caps lock.
        </p>
      </header>

      <section aria-label="steps" className="space-y-6">
        {STEPS.map((s) => (
          <div key={s.n} className="veloura-card p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-veloura-pink/15 font-heading text-sm text-veloura-pink">
                {s.n}
              </span>
              <h2 className="font-heading text-lg text-veloura-text">{s.title}</h2>
            </div>
            <p className="mt-2.5 pl-11 text-sm leading-relaxed text-veloura-muted">{s.body}</p>
          </div>
        ))}
      </section>

      <section aria-label="step 1 detail" className="mt-10">
        <h2 className="font-heading text-2xl text-veloura-text">step 1 — the invite</h2>
        <p className="mt-2 text-sm leading-relaxed text-veloura-muted">
          the button below opens discord&apos;s authorization page. pick your
          server, review the permissions (they map to her features — kick/ban
          for moderation, manage roles for rewards, embed links for the
          pretty cards) and authorize.
        </p>
        {invite && (
          <p className="mt-4">
            <a
              href={invite}
              target="_blank"
              rel="noopener noreferrer"
              className="veloura-button-primary px-6 text-sm"
            >
              <Icon name="plus" size={15} />
              add aurelia to discord
            </a>
          </p>
        )}
        <CodeBlock title="permissions she asks for">
          kick · ban · timeout members · manage channels/messages/roles · embed
          links · attach files · read history · add reactions · threads ·
          voice (connect/speak/mute/move) · webhooks · nicknames
        </CodeBlock>
        <p className="text-xs leading-relaxed text-veloura-muted/70">
          she never asks for administrator. every permission maps to a
          feature you can see in{' '}
          <Link href="/docs/commands" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            the command reference
          </Link>
          .
        </p>
      </section>

      <section aria-label="step 2 detail" className="mt-10">
        <h2 className="font-heading text-2xl text-veloura-text">step 2 — the wizard</h2>
        <p className="mt-2 text-sm leading-relaxed text-veloura-muted">
          in any channel she can see (the response is ephemeral — only you
          see it), run:
        </p>
        <CodeBlock title="discord">/setup</CodeBlock>
        <p className="mt-2 text-sm leading-relaxed text-veloura-muted">
          you&apos;ll pick features from a multi-select, choose channels with
          real channel pickers, and get a summary with test buttons at the
          end. everything it writes can be changed later — in discord with
          slash commands or visually in the{' '}
          <Link href="/docs/dashboard" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            dashboard guide
          </Link>
          .
        </p>
      </section>

      <section aria-label="step 3 detail" className="mt-10">
        <h2 className="font-heading text-2xl text-veloura-text">step 3 — three ways to talk</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            {
              title: 'slash commands',
              sample: '/daily',
              desc: 'the full menu — type / and browse. every feature, every option.',
            },
            {
              title: '@aurelia natural language',
              sample: '@aurelia remind me in 10m to stretch',
              desc: 'say it like a human — she parses intents: reminders, moderation, questions.',
            },
            {
              title: 'classic prefix',
              sample: 'a!level',
              desc: 'for the old souls. the prefix is configurable with /prefix set.',
            },
          ].map((w) => (
            <div key={w.title} className="veloura-card p-4">
              <h3 className="text-sm font-medium text-veloura-text">{w.title}</h3>
              <code className="mt-2 block rounded-[8px] bg-veloura-navy px-2.5 py-1.5 font-mono text-[11px] text-veloura-pink">
                {w.sample}
              </code>
              <p className="mt-2 text-xs leading-relaxed text-veloura-muted">{w.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-label="next steps" className="mt-10">
        <h2 className="font-heading text-2xl text-veloura-text">where to go next</h2>
        <ul className="mt-4 space-y-2.5 text-sm">
          {[
            { href: '/docs/commands', label: 'the full command reference — all 167 commands' },
            { href: '/docs/modules/welcome', label: 'start with the welcome module guide' },
            { href: '/docs/dashboard', label: 'configure everything visually in the dashboard' },
            { href: '/docs/faq', label: 'pricing, data and self-hosting questions' },
          ].map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <ShareButtons compact className="mt-10 no-print" text="getting started with aurelia, the soft discord bot ✦" />
    </>
  );
}
