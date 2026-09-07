'use client';

/**
 * app/docs/commands/page.tsx — the full command reference.
 *
 * Renders DOCS_COMMANDS (auto-generated from COMMANDS.md) with:
 *   · category chips + free-text filter (client-side, instant)
 *   · per-command cards anchored at #<name> so the sidebar search and
 *     the landing command grid deep-link straight to a command
 *   · collapsible subcommand blocks
 *   · examples rendered as copyable CodeBlocks
 *
 * The URL hash scrolls to the command after render (native browser
 * behavior + a manual scrollIntoView for late hydration).
 */

import { useEffect, useMemo, useState } from 'react';

import { CodeBlock } from '@/components/docs/CodeBlock';
import { Markdown, renderInline } from '@/components/docs/Markdown';
import { ShareButtons } from '@/components/site/ShareButtons';
import { cn } from '@/lib/format';
import { COMMAND_COUNT } from '@/lib/marketing';
import type { DocsCommand } from '@/lib/docs-commands-data';
import { DOCS_COMMANDS, DOCS_COMMAND_COUNT } from '@/lib/docs-commands-data';

function anchor(cmd: DocsCommand): string {
  return cmd.name.replace('/', '').replace(/\s+/g, '-');
}

export function CommandsClient() {
  const [category, setCategory] = useState<string>('all');
  const [query, setQuery] = useState('');
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

  const cats = useMemo(
    () => ['all', ...DOCS_COMMANDS.map((c) => c.category)],
    [],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return DOCS_COMMANDS.filter((cat) => {
      if (category !== 'all' && cat.category !== category) return false;
      if (!q) return true;
      return cat.commands.some(
        (cmd) =>
          cmd.name.toLowerCase().includes(q) ||
          cmd.description.toLowerCase().includes(q) ||
          cmd.subcommands.some((s) => s.name.toLowerCase().includes(q)),
      );
    }).map((cat) => ({
      ...cat,
      commands: q
        ? cat.commands.filter(
            (cmd) =>
              cmd.name.toLowerCase().includes(q) ||
              cmd.description.toLowerCase().includes(q) ||
              cmd.subcommands.some((s) => s.name.toLowerCase().includes(q)),
          )
        : cat.commands,
    }));
  }, [category, query]);

  const visibleCount = filtered.reduce((n, c) => n + c.commands.length, 0);

  // scroll to the #hash command after hydration
  useEffect(() => {
    if (window.location.hash) {
      const el = document.getElementById(
        decodeURIComponent(window.location.hash.slice(1)),
      );
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  return (
    <>
      <header className="mb-6">
        <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">reference</p>
        <h1 className="font-heading mt-2 text-4xl text-veloura-text">every command ✦</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
          all {COMMAND_COUNT} commands ({DOCS_COMMAND_COUNT} root entries +
          subcommands), lifted straight from the audited{' '}
          <code className="rounded bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[11px] text-veloura-lavender">
            COMMANDS.md
          </code>{' '}
          — permissions, cooldowns and examples included. search from the
          sidebar to jump straight to one.
        </p>
        <ShareButtons compact className="mt-4 no-print" />
      </header>

      {/* filter bar */}
      <div className="no-print sticky top-16 z-20 -mx-1 mb-8 space-y-3 border-b border-veloura-border/60 bg-veloura-navy/95 px-1 pb-4 pt-3 backdrop-blur-md">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filter commands… (e.g. “warn”)"
          aria-label="filter the command list"
          className="veloura-input !py-2 text-sm"
        />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="filter by category">
          {cats.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              className={cn(
                'rounded-full px-3 py-1 text-[11px] transition',
                category === c
                  ? 'bg-veloura-pink text-veloura-navy-deep'
                  : 'bg-veloura-card-hover text-veloura-muted hover:text-veloura-text',
              )}
              aria-pressed={category === c}
            >
              {c === 'all' ? `all (${DOCS_COMMAND_COUNT})` : c.toLowerCase()}
            </button>
          ))}
        </div>
        {query && (
          <p className="text-xs text-veloura-muted/70" aria-live="polite">
            {visibleCount} command{visibleCount === 1 ? '' : 's'} match “{query}”
          </p>
        )}
      </div>

      {/* command sections */}
      <div className="space-y-12">
        {filtered.map((cat) => (
          <section key={cat.category} aria-label={cat.category}>
            <h2 className="font-heading text-2xl text-veloura-text">
              {cat.category.toLowerCase()}
              <span className="ml-2 text-sm font-normal text-veloura-muted/60">
                {cat.commands.length}
              </span>
            </h2>

            <div className="mt-4 space-y-4">
              {cat.commands.map((cmd) => (
                <article
                  key={cmd.name}
                  id={anchor(cmd)}
                  className="veloura-card scroll-mt-36 p-5"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-mono text-base text-veloura-pink">
                      {cmd.name}
                    </h3>
                    {cmd.isGroup && (
                      <span className="rounded-full bg-veloura-lavender/15 px-2 py-0.5 text-[10px] uppercase tracking-wider text-veloura-lavender">
                        group
                      </span>
                    )}
                    {cmd.isNew && (
                      <span className="rounded-full bg-veloura-success/15 px-2 py-0.5 text-[10px] uppercase tracking-wider text-veloura-success">
                        newer
                      </span>
                    )}
                    {cmd.permission && (
                      <span className="rounded-full bg-veloura-danger/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-veloura-danger">
                        {cmd.permission.toLowerCase()}
                      </span>
                    )}
                    {cmd.cooldown && (
                      <span className="ml-auto flex items-center gap-1 text-[11px] text-veloura-muted/70">
                        <span aria-hidden>⏱</span>
                        {cmd.cooldown}
                      </span>
                    )}
                  </div>

                  {cmd.description && (
                    <Markdown
                      text={cmd.description}
                      className="mt-2.5 text-sm leading-relaxed text-veloura-muted"
                    />
                  )}

                  {cmd.params.length > 0 && (
                    <div className="mt-4">
                      <p className="text-[11px] uppercase tracking-wider text-veloura-muted/70">
                        parameters
                      </p>
                      <ul className="mt-1.5 space-y-1">
                        {cmd.params.map((p) => (
                          <li key={p} className="text-xs leading-relaxed text-veloura-muted">
                            {renderInline(p)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {cmd.examples.length > 0 && (
                    <div className="mt-4">
                      <p className="mb-1 text-[11px] uppercase tracking-wider text-veloura-muted/70">
                        examples
                      </p>
                      {cmd.examples
                        .filter((e) => !e.startsWith('response:'))
                        .map((e) => (
                          <CodeBlock key={e} title="discord" className="!my-1.5">
                            {e.replace(/^`|`$/g, '')}
                          </CodeBlock>
                        ))}
                      {cmd.examples
                        .filter((e) => e.startsWith('response:'))
                        .map((e) => (
                          <p key={e} className="mt-1.5 text-xs italic leading-relaxed text-veloura-muted/80">
                            {renderInline(e.slice('response: '.length))}
                          </p>
                        ))}
                    </div>
                  )}

                  {cmd.other.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {cmd.other.map((o) => (
                        <li key={o} className="text-xs leading-relaxed text-veloura-muted/80">
                          {renderInline(o)}
                        </li>
                      ))}
                    </ul>
                  )}

                  {cmd.subcommands.length > 0 && (
                    <div className="mt-4 border-t border-veloura-border/60 pt-3">
                      <button
                        type="button"
                        onClick={() =>
                          setOpenGroups((g) => ({
                            ...g,
                            [cmd.name]: !(g[cmd.name] ?? false),
                          }))
                        }
                        aria-expanded={openGroups[cmd.name] ?? false}
                        className="flex items-center gap-2 text-xs font-medium text-veloura-lavender"
                      >
                        <span
                          className={cn(
                            'transition-transform',
                            (openGroups[cmd.name] ?? false) && 'rotate-90',
                          )}
                          aria-hidden
                        >
                          ▸
                        </span>
                        {cmd.subcommands.length} subcommand
                        {cmd.subcommands.length === 1 ? '' : 's'}
                      </button>

                      {(openGroups[cmd.name] ?? false) && (
                        <div className="mt-3 space-y-3">
                          {cmd.subcommands.map((sub) => (
                            <div key={sub.name} className="rounded-[12px] bg-veloura-navy/60 p-3.5">
                              <p className="font-mono text-xs text-veloura-pink">{sub.name}</p>
                              {sub.description && (
                                <Markdown
                                  text={sub.description}
                                  className="mt-1.5 text-xs leading-relaxed text-veloura-muted"
                                />
                              )}
                              {sub.body.length > 0 && (
                                <ul className="mt-2 space-y-1">
                                  {sub.body.map((b, i) => (
                                    <li key={i} className="text-xs leading-relaxed text-veloura-muted/80">
                                      {renderInline(b.replace(/^- /, ''))}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        ))}

        {visibleCount === 0 && (
          <p className="py-16 text-center text-sm text-veloura-muted">
            nothing matches “{query}” — try the sidebar search to look inside
            every command ♡
          </p>
        )}
      </div>
    </>
  );
}
