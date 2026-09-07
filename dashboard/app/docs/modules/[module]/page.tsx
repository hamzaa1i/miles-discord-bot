import Link from 'next/link';
import { notFound } from 'next/navigation';

import { CodeBlock } from '@/components/docs/CodeBlock';
import { Markdown } from '@/components/docs/Markdown';
import { ShareButtons } from '@/components/site/ShareButtons';
import { MODULE_DOCS, moduleDoc } from '@/lib/docs-modules';
import { pageMetadata } from '@/lib/seo';

/**
 * app/docs/modules/[module]/page.tsx — per-module deep dive.
 *
 * Statically generated for every module in MODULE_DOCS (build-time,
 * no runtime db). Each page: what/why, the commands that drive it,
 * config notes, cross-links to the previous/next module and the
 * commands reference.
 */

type Params = { params: { module: string } };

export function generateStaticParams() {
  return MODULE_DOCS.map((m) => ({ module: m.slug }));
}

export function generateMetadata({ params }: Params) {
  const doc = moduleDoc(params.module);
  if (!doc) return pageMetadata({ title: 'module not found', description: '', path: '/docs/modules' });
  return pageMetadata({
    title: `${doc.title} module`,
    description: `${doc.tagline} — ${doc.description.slice(0, 130)}…`,
    path: `/docs/modules/${doc.slug}`,
  });
}

export default function ModulePage({ params }: Params) {
  const doc = moduleDoc(params.module);
  if (!doc) notFound();

  const idx = MODULE_DOCS.findIndex((m) => m.slug === doc.slug);
  const prev = idx > 0 ? MODULE_DOCS[idx - 1] : null;
  const next = idx < MODULE_DOCS.length - 1 ? MODULE_DOCS[idx + 1] : null;

  return (
    <>
      <nav aria-label="breadcrumb" className="mb-4 text-xs text-veloura-muted/70">
        <Link href="/docs" className="hover:text-veloura-pink">docs</Link>
        <span aria-hidden> / </span>
        <Link href="/docs/modules" className="hover:text-veloura-pink">modules</Link>
        <span aria-hidden> / </span>
        <span className="text-veloura-text">{doc.title}</span>
      </nav>

      <header className="mb-8">
        <h1 className="font-heading text-4xl text-veloura-text">{doc.title}</h1>
        <p className="mt-2 text-sm text-veloura-lavender">“{doc.tagline}”</p>
      </header>

      <Markdown text={doc.description} className="text-[15px] leading-relaxed text-veloura-muted" />

      <section aria-label="commands" className="mt-8">
        <h2 className="font-heading text-xl text-veloura-text">commands</h2>
        <p className="mt-1.5 text-sm text-veloura-muted">
          the slash commands behind this module — full details in the{' '}
          <Link href="/docs/commands" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            command reference
          </Link>
          :
        </p>
        <ul className="mt-4 space-y-2">
          {doc.commands.map((c) => (
            <li key={c}>
              <code className="rounded-[8px] bg-veloura-card-hover px-2.5 py-1.5 font-mono text-xs text-veloura-pink">
                {c}
              </code>
            </li>
          ))}
        </ul>
      </section>

      {doc.notes && doc.notes.length > 0 && (
        <section aria-label="tips" className="mt-8">
          <h2 className="font-heading text-xl text-veloura-text">soft tips</h2>
          <ul className="mt-3 space-y-2.5">
            {doc.notes.map((n) => (
              <li key={n} className="veloura-card flex gap-3 p-4 text-sm leading-relaxed text-veloura-muted">
                <span className="mt-0.5 text-veloura-pink" aria-hidden>✦</span>
                {n}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="configure" className="mt-8">
        <h2 className="font-heading text-xl text-veloura-text">configure it</h2>
        <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">
          two ways: slash commands in discord, or visually in the{' '}
          <Link href="/login" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            dashboard
          </Link>
          . the wizard can do the essentials in one command:
        </p>
        <CodeBlock title="discord">/setup</CodeBlock>
      </section>

      <ShareButtons compact className="mt-10 no-print" text={`aurelia's ${doc.title} module — ${doc.tagline}:`} />

      <nav aria-label="module pagination" className="no-print mt-8 flex items-center justify-between gap-4 border-t border-veloura-border/60 pt-6 text-sm">
        {prev ? (
          <Link href={`/docs/modules/${prev.slug}`} className="group text-veloura-muted hover:text-veloura-pink">
            <span className="block text-[11px] uppercase tracking-wider text-veloura-muted/60">← previous</span>
            <span className="group-hover:underline">{prev.title}</span>
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={`/docs/modules/${next.slug}`} className="group text-right text-veloura-muted hover:text-veloura-pink">
            <span className="block text-[11px] uppercase tracking-wider text-veloura-muted/60">next →</span>
            <span className="group-hover:underline">{next.title}</span>
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </>
  );
}
