'use client';

/** Sidebar — module navigation, organized by category (desktop fixed / mobile drawer).
 *
 * Every item links to its OWN dedicated route (no hash fragments) and
 * the active check is an EXACT pathname match — live testing showed
 * prefix matching highlighted three items at once and hash routes
 * fought the browser scroll. One item, one page, one highlight.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SIDEBAR } from '@/lib/modules';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';

export function Sidebar({ guildId, onNavigate }: { guildId: string; onNavigate?: () => void }) {
  const pathname = usePathname();

  // pathname = /servers/<gid>/<rest...>
  const rest = pathname.replace(/^\/servers\/[^/]+\/?/, '');

  function isActive(route: string): boolean {
    return route === '' ? rest === '' : rest === route;
  }

  return (
    <nav aria-label="module navigation" className="flex h-full flex-col overflow-y-auto px-3 pb-6 pt-2">
      {SIDEBAR.map((cat) => (
        <div key={cat.label} className="mb-4">
          <p className="mb-2 flex items-center gap-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-veloura-muted/70">
            <Icon name={cat.icon} size={12} className="text-veloura-lavender/60" />
            {cat.label}
          </p>
          <ul className="space-y-0.5">
            {cat.items.map((item) => {
              const href = item.route
                ? `/servers/${guildId}/${item.route}`
                : `/servers/${guildId}`;
              const active = isActive(item.route);
              return (
                <li key={`${cat.label}-${item.title}`}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'flex min-h-[40px] items-center gap-2.5 rounded-[10px] px-3 text-sm transition',
                      active
                        ? 'bg-veloura-pink/10 text-veloura-pink shadow-glow'
                        : 'text-veloura-muted hover:bg-veloura-card-hover hover:text-veloura-text',
                    )}
                  >
                    <Icon
                      name={item.icon}
                      size={15}
                      className={cn('w-4 shrink-0', active ? 'text-veloura-pink' : 'text-veloura-lavender/70')}
                    />
                    <span className="truncate">{item.title}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}

      {/* PHASE N (19.2) — site escape hatches pinned at the bottom of
          the module nav: home (landing) + all servers. Nobody gets
          stranded inside the guild dashboard. */}
      <div className="mt-auto border-t border-veloura-border/60 pt-3">
        <Link
          href="/servers"
          onClick={onNavigate}
          className="flex min-h-[36px] items-center gap-2.5 rounded-[10px] px-3 text-[13px] text-veloura-muted transition hover:bg-veloura-card-hover hover:text-veloura-text"
        >
          <Icon name="hash" size={14} className="w-4 shrink-0 text-veloura-lavender/70" />
          all servers
        </Link>
        <Link
          href="/"
          onClick={onNavigate}
          className="flex min-h-[36px] items-center gap-2.5 rounded-[10px] px-3 text-[13px] text-veloura-muted transition hover:bg-veloura-card-hover hover:text-veloura-pink"
        >
          <Icon name="star" size={14} className="w-4 shrink-0 text-veloura-lavender/70" />
          aurelia home
        </Link>
      </div>
    </nav>
  );
}
