import Link from 'next/link';

import { DocsBreadcrumb } from '@/components/docs/DocsBreadcrumb';
import { ShareButtons } from '@/components/site/ShareButtons';
import { SUPPORT_SERVER_URL } from '@/lib/marketing';
import { pageMetadata } from '@/lib/seo';

/**
 * app/docs/faq/page.tsx — the docs-side faq (deeper than the landing
 * page's five). Native <details> elements — keyboard + print friendly.
 *
 * PHASE N: self-host / MIT / github-issues copy replaced (source is
 * privately maintained; the support server is the bug channel), and
 * the AI answers describe the multi-provider routing honestly.
 */

export const metadata = pageMetadata({
  title: 'faq',
  description:
    'is aurelia free? what data does she collect? which ai powers her? the soft questions and their soft answers.',
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
        on free-tier providers with automatic failover. if she saves you
        time, a coffee is always appreciated but never required.
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
        aurelia is currently hosted and maintained as a managed project —
        the source repository is private. that is separate from using her:
        anyone can add the bot to their server for free (see the{' '}
        <Link href="/docs/getting-started" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
          getting-started guide
        </Link>
        ), and she runs as one shared, carefully tended instance. the
        support server is the place to ask if you need something
        self-host-shaped.
      </>
    ),
  },
  {
    q: 'which ai models power her?',
    a: (
      <>
        several, behind one router. everyday chat starts on gemini flash;
        mistral small answers as fallback and handles sensitive work
        (moderation, automod) by default; a glm reasoning model takes the
        genuinely hard questions under a daily budget; and groq models are
        the emergency floor that keeps her talking when everything else
        is rate-limited. whichever answers, responses are post-processed
        so reasoning never leaks into chat — only the answer does. see{' '}
        <Link href="/docs/faq#ai-privacy" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
          the ai privacy notes
        </Link>{' '}
        below.
      </>
    ),
  },
  {
    q: 'what does multi-provider ai mean for my privacy?',
    a: (
      <>
        <span id="ai-privacy" />aurelia can use multiple external ai
        inference providers, and which one serves a request depends on the
        request type and live provider availability. the rules: only the
        minimum context a feature needs is sent; moderation and automod
        traffic is routed to providers chosen for stricter data terms by
        default (never the free-tier consumer endpoints unless explicitly
        configured); your <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px] text-veloura-lavender">/privacy</code>{' '}
        opt-outs are enforced before any provider is invoked; provider
        telemetry stores counts and latencies, never conversations; and
        api keys stay server-side — none ever reach the browser.
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
        is fastest. bug reports and feature requests both land there —
        they go straight into the build queue.
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
      <DocsBreadcrumb page="faq" />

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
