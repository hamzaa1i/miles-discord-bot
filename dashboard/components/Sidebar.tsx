'use client';

/** Sidebar — module navigation, organized by category (desktop fixed / mobile drawer).
 *
 * Active-item matching is EXACT on the page path plus the URL hash:
 *  - /roles#onboarding highlights only "onboarding" (not all four roles
 *    items — the old startsWith() bug highlighted three at once),
 *  - /automod highlights only "ai automod",
 *  - /stats highlights only "statistics".
 */

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { SIDEBAR } from '@/lib/modules';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';

export function Sidebar({ guildId, onNavigate }: { guildId: string; onNavigate?: () => void }) {
  const pathname = usePathname();
  const [hash, setHash] = useState<string>('');

  // track the URL fragment so #tab links light the right item live
  useEffect(() => {
    const update = () => setHash(window.location.hash);
    update();
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);

  // pathname = /servers/<gid>/<rest...>
  const rest = pathname.replace(/^\/servers\/[^/]+\/?/, '');
  const bareHash = hash.replace(/^#/, '');

  function isActive(route: string): boolean {
    const target = route.split('#')[0];
    const targetHash = route.split('#')[1];
    if (!target) {
      return rest === '' && !bareHash;
    }
    const pathMatches = rest === target || rest.startsWith(`${target}/`);
    if (targetHash) {
      return pathMatches && bareHash === targetHash;
    }
    return pathMatches && !bareHash;
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
              const base = item.route.split('#')[0];
              const href = base ? `/servers/${guildId}/${base}` : `/servers/${guildId}`;
              const active = isActive(item.route);
              return (
                <li key={`${cat.label}-${item.title}`}>
                  <Link
                    href={item.route.includes('#') ? `${href}${item.route.slice(item.route.indexOf('#'))}` : href}
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
    </nav>
  );
}
