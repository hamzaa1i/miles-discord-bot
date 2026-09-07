import Link from 'next/link';

import { ShareButtons } from '@/components/site/ShareButtons';
import { GITHUB_URL, SUPPORT_SERVER_URL } from '@/lib/marketing';
import { pageMetadata } from '@/lib/seo';

/**
 * app/docs/faq/page.tsx — the docs-side faq (deeper than the landing
 * page's five). Native <details> elements — keyboard + print friendly.
 */

export const metadata = pageMetadata({
  title: 'faq',
  description:
    'is aurelia free? what data does she collect? can i self-host? the soft questions and their soft answers.',
  path: '/docs/faq',
});

const QA: { q: string; a: React.ReactNode }[] = [
  {
    q: 'is aurelia really free?',
    a: (
      <>
        yes — every command, every dashboard page, every module. there is no
        premium tier, no paywalled feature, no ad. hosting is covered by
        <span className="text-veloura-pink"> @volc</span> and inference runs
        on groq&apos;s free tier. if she saves you time, a coffee is always
        appreciated but never required.
      </>
    ),
  },
  {
    q: 'what data does she collect?',
    a: (
      <>
        the minimum for each feature to work: conversation history (last 20
        messages per user per channel) for ai chat, a capped list of durable
        facts for memory, xp counters for leveling, warnings for moderation,
        and feature settings per server. no analytics, no third-party
        trackers, no selling anything. see{' '}
        <Link href="/docs/modules/privacy" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
          the privacy module guide
        </Link>{' '}
        for the full controls.
      </>
    ),
  },
  {
    q: 'can i export or delete my data?',
    a: (
      <>
        both, built in:{' '}
        <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px] text-veloura-lavender">
          /privacy export
        </code>{' '}
        gives you everything as json,{' '}
        <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px] text-veloura-lavender">
          /privacy delete
        </code>{' '}
        erases it everywhere after a double confirmation. per-feature
        opt-outs are one command away too.
      </>
    ),
  },
  {
    q: 'can i self-host?',
    a: (
      <>
        yes — MIT licensed. you need python 3.11+, a discord bot token, a
        free groq api key and (optionally) a free supabase project for
        persistent data. the{' '}
        <Link href="/docs/getting-started" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
          getting-started guide
        </Link>{' '}
        and{' '}
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
          the repository readme
        </a>{' '}
        cover the rest, including the dashboard and render deployment.
      </>
    ),
  },
  {
    q: 'which ai model powers her?',
    a: (
      <>
        groq-hosted open models: a mid-size model for conversation and
        fast models for utility intents, with reasoning escalations for
        hard questions. responses are post-processed so reasoning never
        leaks into chat — only the answer does.
      </>
    ),
  },
  {
    q: 'how do i report a bug or request a feature?',
    a: (
      <>
        {SUPPORT_SERVER_URL ? (
          <a href={SUPPORT_SERVER_URL} target="_blank" rel="noopener noreferrer" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            the support server
          </a>
        ) : (
          'the support server (link coming soon)'
        )}{' '}
        is fastest;{' '}
        <a href={`${GITHUB_URL}/issues`} target="_blank" rel="noopener noreferrer" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
          github issues
        </a>{' '}
        work great too and land directly in the build queue.
      </>
    ),
  },
  {
    q: 'does she work in multiple servers?',
    a: (
      <>
        yes — settings, xp, warnings and ai memory are all per-server, and
        the dashboard lists every server where you hold the manage server
        permission. reminders follow you across servers because they are
        per-user.
      </>
    ),
  },
  {
    q: 'what happens if she goes offline?',
    a: (
      <>
        reminders and recurring tasks catch up on restart by design —
        nothing fires twice, nothing is lost. the{' '}
        <Link href="/stats" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
          public stats page
        </Link>{' '}
        shows live vitals and uptime history.
      </>
    ),
  },
];

export default function FaqPage() {
  return (
    <>
      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">faq</p>
        <h1 className="font-heading mt-2 text-4xl text-veloura-text">soft questions, soft answers ✦</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
          the questions that land in every support thread, answered once
          here. still stuck? the support server is one click away.
        </p>
      </header>

      <div className="space-y-3">
        {QA.map((item) => (
          <details key={item.q} className="veloura-card group px-5 py-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-veloura-text marker:hidden [&::-webkit-details-marker]:hidden">
              {item.q}
              <span className="text-veloura-pink transition-transform duration-300 group-open:rotate-45" aria-hidden>
                ✦
              </span>
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-veloura-muted">{item.a}</p>
          </details>
        ))}
      </div>

      <ShareButtons compact className="mt-10 no-print" />
    </>
  );
}
