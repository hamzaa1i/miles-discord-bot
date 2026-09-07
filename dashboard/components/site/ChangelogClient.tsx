'use client';

/**
 * app/changelog/page.tsx — PHASE M PART 5.
 *
 * Chronological release notes with category tags (feature / fix /
 * improvement / breaking) and a filter row. Data comes from
 * lib/changelog-data.ts (auto-generated with CHANGELOG.md). The rss
 * mirror lives at /changelog.rss and the json api at /api/changelog.
 */

import Link from 'next/link';
import { useMemo, useState } from 'react';

import { Icon } from '@/components/icons';
import { ShareButtons } from '@/components/site/ShareButtons';
import { SiteFooter } from '@/components/site/SiteFooter';
import { SiteHeader } from '@/components/site/SiteHeader';
import { cn } from '@/lib/format';
import { CHANGELOG, LATEST_VERSION } from '@/lib/changelog-data';

const CATS = ['all', 'feature', 'fix', 'improvement', 'breaking'] as const;
type Cat = (typeof CATS)[number];
type EntryCat = Exclude<Cat, 'all'>;

const CAT_META: Record<Cat, { label: string; color: string }> = {
  all: { label: 'all', color: 'bg-veloura-card-hover text-veloura-muted' },
  feature: { label: 'feature', color: 'bg-veloura-pink/15 text-veloura-pink' },
  fix: { label: 'fix', color: 'bg-veloura-success/15 text-veloura-success' },
  improvement: { label: 'improvement', color: 'bg-veloura-lavender/15 text-veloura-lavender' },
  breaking: { label: 'breaking', color: 'bg-veloura-danger/15 text-veloura-danger' },
};

export function ChangelogClient() {
  const [cat, setCat] = useState<Cat>('all');

  const versions = useMemo(
    () =>
      CHANGELOG.map((v) => {
        if (cat === 'all') return v;
        const entries = v.categories[cat];
        if (!entries || entries.length === 0) return null;
        return { ...v, categories: { [cat]: entries } } as typeof v;
      }).filter((v): v is (typeof CHANGELOG)[number] => v !== null),
    [cat],
  );

  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <header className="mb-8">
          <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">changelog</p>
          <h1 className="font-heading mt-2 text-4xl text-veloura-text">
            every change, softly noted ✦
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-veloura-muted">
            currently singing:{' '}
            <span className="text-veloura-pink">{LATEST_VERSION}</span> — new
            releases land here, in the{' '}
            <a href="/changelog.rss" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
              rss feed
            </a>{' '}
            and at{' '}
            <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px] text-veloura-lavender">
              /api/changelog
            </code>
            .
          </p>
          <ShareButtons compact className="mt-4 no-print" text="aurelia just shipped — see the changelog ✦" />
        </header>

        {/* category filter */}
        <div className="no-print sticky top-16 z-20 -mx-1 mb-8 border-b border-veloura-border/60 bg-veloura-navy/95 px-1 pb-3 pt-3 backdrop-blur-md">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="filter by category">
            {CATS.map((c) => {
              const count = CHANGELOG.reduce(
                (n, v) => n + (c === 'all' ? 1 : v.categories[c]?.length ?? 0),
                0,
              );
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCat(c)}
                  disabled={c !== 'all' && count === 0}
                  aria-pressed={cat === c}
                  className={cn(
                    'rounded-full px-3 py-1 text-[11px] transition disabled:opacity-40',
                    cat === c
                      ? 'bg-veloura-pink text-veloura-navy-deep'
                      : 'bg-veloura-card-hover text-veloura-muted hover:text-veloura-text',
                  )}
                >
                  {CAT_META[c].label} · {count}
                </button>
              );
            })}
          </div>
        </div>

        {/* versions */}
        <div className="space-y-8">
          {versions.map((v) => (
            <article key={v.version} className="veloura-card relative p-6">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-veloura-pink/40 to-transparent"
              />
              <header className="flex flex-wrap items-baseline gap-3">
                <h2 className="font-heading text-2xl text-veloura-pink">{v.version}</h2>
                <time className="text-xs text-veloura-muted/70">{v.date}</time>
              </header>

              {v.summary && (
                <p className="mt-2.5 text-sm leading-relaxed text-veloura-muted">{v.summary}</p>
              )}

              {v.highlights.length > 0 && (
                <ul className="mt-4 flex flex-wrap gap-1.5">
                  {v.highlights.map((h) => (
                    <li
                      key={h}
                      className="rounded-full bg-veloura-lavender/10 px-2.5 py-1 text-[11px] text-veloura-lavender"
                    >
                      ✦ {h}
                    </li>
                  ))}
                </ul>
              )}

              <div className="mt-5 space-y-4">
                {(Object.keys(v.categories) as EntryCat[])
                  .filter((k) => v.categories[k]?.length > 0)
                  .map((k) => (
                    <section key={k} aria-label={`${k} changes`}>
                      <div className="flex items-center gap-2">
                        <span className={cn('rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider', CAT_META[k].color)}>
                          {CAT_META[k].label}
                        </span>
                        <span className="text-[11px] text-veloura-muted/60">
                          {v.categories[k].length} change{v.categories[k].length === 1 ? '' : 's'}
                        </span>
                      </div>
                      <ul className="mt-2 space-y-1.5">
                        {v.categories[k].map((entry) => (
                          <li key={entry} className="flex gap-2 text-sm leading-relaxed text-veloura-muted">
                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-veloura-pink/60" aria-hidden />
                            {entry}
                          </li>
                        ))}
                      </ul>
                    </section>
                  ))}
              </div>
            </article>
          ))}
        </div>

        <p className="mt-8 text-center text-xs text-veloura-muted/60">
          generated from git history ·{' '}
          <Link href="/docs/api" className="text-veloura-pink hover:underline">
            get it as json or rss
          </Link>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
