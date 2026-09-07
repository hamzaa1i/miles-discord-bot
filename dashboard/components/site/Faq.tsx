/**
 * components/site/Faq.tsx — PHASE M PART 1 §7 (maintained through N).
 *
 * Accessible FAQ using native <details>/<summary> (keyboard + screen
 * reader friendly, zero js). Content is mirrored on /docs/faq.
 *
 * PHASE N: self-host / MIT copy replaced with the managed-project
 * wording (source is privately maintained), and the AI answers now
 * describe the multi-provider routing honestly — including the
 * sensitive-data privacy story.
 */

import Link from 'next/link';
import { SUPPORT_SERVER_URL } from '@/lib/marketing';

const QA: { q: string; a: React.ReactNode }[] = [
  {
    q: 'is it really free?',
    a: (
      <>
        yes — completely. no paywalls, no premium tiers, no ads, no
        locked features. aurelia is hosted with love by{' '}
        <span className="text-veloura-pink">@volc</span> and the source is
        privately maintained — adding her to your server costs nothing,
        ever.
      </>
    ),
  },
  {
    q: 'what data do you collect?',
    a: (
      <>
        the minimum needed to remember you: conversation history per
        channel (last 20 messages), a few durable facts per user, and
        feature settings per server. you can{' '}
        <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px]">
          /privacy export
        </code>{' '}
        everything as json or{' '}
        <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px]">
          /privacy delete
        </code>{' '}
        it all, any time.
      </>
    ),
  },
  {
    q: 'can i self-host?',
    a: (
      <>
        aurelia is currently hosted and maintained as a managed project
        — the source repository is private. installation and source
        access are separate things: anyone can{' '}
        <Link
          href="/docs/getting-started"
          className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2"
        >
          add her to their server
        </Link>{' '}
        for free, but she runs as one shared, carefully tended instance.
      </>
    ),
  },
  {
    q: 'which ai powers her — and what about privacy?',
    a: (
      <>
        aurelia routes each request across multiple external ai
        providers (gemini for everyday chat, mistral for fallback and
        sensitive work, a glm reasoning model for hard questions, groq as
        the emergency floor) depending on the request type and live
        provider health. only the minimum context a feature needs is
        ever sent; moderation and automod traffic is routed to providers
        chosen specifically for stricter data terms by default; your{' '}
        <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px]">
          /privacy
        </code>{' '}
        opt-outs are enforced before any provider is called; and nothing
        you say is written into analytics — provider telemetry stores
        counts and latencies, never conversations.
      </>
    ),
  },
  {
    q: 'how do i get help?',
    a: (
      <>
        the{' '}
        <Link
          href="/docs"
          className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2"
        >
          documentation
        </Link>{' '}
        covers every command and module, and{' '}
        {SUPPORT_SERVER_URL ? (
          <a
            href={SUPPORT_SERVER_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2"
          >
            the support server
          </a>
        ) : (
          'the support server (link coming soon)'
        )}{' '}
        is where the humans hang out.
      </>
    ),
  },
  {
    q: 'does the ai cost anything?',
    a: (
      <>
        no — the router prefers free-tier inference everywhere and fails
        over automatically, so there are no per-message charges and no
        usage caps for normal servers. heavy reasoning calls are
        budget-guarded to keep her sustainable, and normal chat never
        touches the expensive routes.
      </>
    ),
  },
];

export function Faq() {
  return (
    <section aria-label="frequently asked questions" className="scroll-mt-20">
      <div className="mx-auto max-w-3xl px-6">
        <header className="mb-10 text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">
            curious?
          </p>
          <h2 className="font-heading mt-2 text-3xl text-veloura-text sm:text-4xl">
            soft questions, soft answers
          </h2>
        </header>

        <div className="space-y-3">
          {QA.map((item) => (
            <details key={item.q} className="veloura-card group px-5 py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-veloura-text marker:hidden [&::-webkit-details-marker]:hidden">
                {item.q}
                <span
                  className="text-veloura-pink transition-transform duration-300 group-open:rotate-45"
                  aria-hidden
                >
                  ✦
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-veloura-muted">
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
