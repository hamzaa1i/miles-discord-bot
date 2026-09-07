'use client';

/**
 * components/docs/DocsSidebar.tsx — Docusaurus-style docs navigation.
 *
 * Sticky sidebar with:
 *   · fuzzy search (Fuse.js, PHASE M PART 2 requirement) — arrow keys
 *     + enter navigate, results drop straight to the anchored command
 *   · section groups (start · modules · reference)
 *   · active-page highlight via exact pathname matching
 * Collapses into a horizontal scroll strip on mobile.
 */

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';
import { MODULE_DOCS } from '@/lib/docs-modules';
import { searchDocs, type SearchEntry } from '@/lib/docs-search';

const START_LINKS = [
  { href: '/docs', label: 'docs home' },
  { href: '/docs/getting-started', label: 'getting started' },
  { href: '/docs/commands', label: 'all commands' },
  { href: '/docs/dashboard', label: 'dashboard guide' },
];

const REFERENCE_LINKS = [
  { href: '/docs/faq', label: 'faq' },
  { href: '/docs/api', label: 'api' },
  { href: '/changelog', label: 'changelog' },
  { href: '/stats', label: 'public stats' },
];

export function DocsSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchEntry[]>([]);
  const [modulesOpen, setModulesOpen] = useState(true);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const r = searchDocs(query);
    setResults(r);
    setActiveIndex(0);
  }, [query]);

  function go(entry: SearchEntry) {
    setQuery('');
    router.push(entry.path);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      go(results[activeIndex]);
    } else if (e.key === 'Escape') {
      setQuery('');
    }
  }

  const isActive = (href: string) =>
    href === '/docs' ? pathname === '/docs' : pathname === href;

  const isModuleActive = pathname.startsWith('/docs/modules/');

  return (
    <aside className="no-print w-full shrink-0 lg:sticky lg:top-20 lg:h-[calc(100vh-6rem)] lg:w-60 lg:overflow-y-auto">
      {/* search */}
      <div className="relative mb-4">
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-veloura-muted/60">
            <Icon name="moon" size={14} />
          </span>
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="search docs… (⌘k)"
            aria-label="search the documentation"
            className="veloura-input !pl-9 !py-2 text-sm"
          />
        </div>

        {query.length >= 2 && (
          <div className="veloura-card absolute z-30 mt-2 max-h-80 w-full overflow-y-auto !p-1.5 shadow-soft">
            {results.length === 0 ? (
              <p className="px-3 py-2.5 text-xs text-veloura-muted">
                nothing found — try “welcome” or “/daily” ♡
              </p>
            ) : (
              results.map((r, i) => (
                <button
                  key={r.path + r.title}
                  type="button"
                  onClick={() => go(r)}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-[8px] px-3 py-2 text-left text-xs transition',
                    i === activeIndex
                      ? 'bg-veloura-card-hover text-veloura-text'
                      : 'text-veloura-muted hover:bg-veloura-card-hover/60',
                  )}
                >
                  <span
                    className={cn(
                      'shrink-0 rounded-full px-1.5 py-0.5 text-[10px] uppercase tracking-wider',
                      r.type === 'command'
                        ? 'bg-veloura-pink/15 text-veloura-pink'
                        : r.type === 'module'
                          ? 'bg-veloura-lavender/15 text-veloura-lavender'
                          : 'bg-veloura-card-hover text-veloura-muted',
                    )}
                  >
                    {r.type}
                  </span>
                  <span className="truncate font-mono">{r.title}</span>
                  <span className="ml-auto hidden truncate text-[10px] text-veloura-muted/60 sm:block">
                    {r.hint}
                  </span>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* nav groups */}
      <nav aria-label="docs navigation" className="space-y-5 text-sm">
        <SidebarGroup label="start">
          {START_LINKS.map((l) => (
            <SidebarLink key={l.href} href={l.href} active={isActive(l.href)}>
              {l.label}
            </SidebarLink>
          ))}
        </SidebarGroup>

        <SidebarGroup label="modules">
          <button
            type="button"
            onClick={() => setModulesOpen((v) => !v)}
            aria-expanded={modulesOpen}
            className={cn(
              'flex w-full items-center gap-2 rounded-[8px] px-3 py-1.5 text-left transition',
              isModuleActive
                ? 'text-veloura-pink'
                : 'text-veloura-muted hover:bg-veloura-card-hover/60 hover:text-veloura-text',
            )}
          >
            <span
              className={cn('text-[10px] transition-transform', modulesOpen && 'rotate-90')}
              aria-hidden
            >
              ▸
            </span>
            <span className="uppercase tracking-wider text-[11px]">all {MODULE_DOCS.length} modules</span>
          </button>
          {modulesOpen && (
            <div className="mt-1 space-y-0.5">
              {MODULE_DOCS.map((m) => (
                <SidebarLink
                  key={m.slug}
                  href={`/docs/modules/${m.slug}`}
                  active={pathname === `/docs/modules/${m.slug}`}
                  indent
                >
                  {m.title}
                </SidebarLink>
              ))}
            </div>
          )}
        </SidebarGroup>

        <SidebarGroup label="reference">
          {REFERENCE_LINKS.map((l) => (
            <SidebarLink key={l.href} href={l.href} active={isActive(l.href)}>
              {l.label}
            </SidebarLink>
          ))}
        </SidebarGroup>
      </nav>
    </aside>
  );
}

function SidebarGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 px-3 text-[11px] uppercase tracking-wider text-veloura-muted/60">
        {label}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function SidebarLink({
  href,
  active,
  indent,
  children,
}: {
  href: string;
  active: boolean;
  indent?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'block rounded-[8px] px-3 py-1.5 text-[13px] transition',
        indent && 'pl-5',
        active
          ? 'bg-veloura-pink/10 text-veloura-pink'
          : 'text-veloura-muted hover:bg-veloura-card-hover/60 hover:text-veloura-text',
      )}
    >
      {children}
    </Link>
  );
}
