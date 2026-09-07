/**
 * components/site/Faq.tsx — PHASE M PART 1 §7.
 *
 * Accessible FAQ using native <details>/<summary> (keyboard + screen
 * reader friendly, zero js). Content is mirrored on /docs/faq.
 */

import Link from 'next/link';
import { GITHUB_URL, SUPPORT_SERVER_URL } from '@/lib/marketing';

const QA: { q: string; a: React.ReactNode }[] = [
  {
    q: 'is it really free?',
    a: (
      <>
        yes — completely. no paywalls, no premium tiers, no ads, no
        locked features. aurelia is hosted with love by{' '}
        <span className="text-veloura-pink">@volc</span> and the code is
        MIT-licensed, so you can even self-host her.
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
        absolutely — she&apos;s MIT licensed. clone the{' '}
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2"
        >
          repository
        </a>
        , add your discord token + a free groq api key, and the{' '}
        <Link
          href="/docs/getting-started"
          className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2"
        >
          getting-started guide
        </Link>{' '}
        walks you through the rest.
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
        no — aurelia runs on groq&apos;s free-tier inference, which is
        fast enough to feel instant. there are no per-message charges
        and no usage caps for normal servers.
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
