'use client';

/** Sidebar — module navigation, organized by category (desktop fixed / mobile drawer). */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SIDEBAR } from '@/lib/modules';
import { cn } from '@/lib/format';

export function Sidebar({ guildId, onNavigate }: { guildId: string; onNavigate?: () => void }) {
  const pathname = usePathname();
  // pathname = /servers/<gid>/<rest...>
  const rest = pathname.replace(/^\/servers\/[^/]+\/?/, '');

  function isActive(route: string): boolean {
    const target = route.split('#')[0];
    if (!target) return rest === '';
    return rest === target || rest.startsWith(`${target}/`);
  }

  return (
    <nav aria-label="module navigation" className="flex h-full flex-col overflow-y-auto px-3 pb-6 pt-2">
      {SIDEBAR.map((cat) => (
        <div key={cat.label} className="mb-4">
          <p className="mb-2 flex items-center gap-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-veloura-muted/70">
            <span aria-hidden>{cat.icon}</span>
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
                      'flex min-h-[38px] items-center gap-2.5 rounded-[10px] px-3 text-sm transition',
                      active
                        ? 'bg-veloura-pink/10 text-veloura-pink shadow-glow'
                        : 'text-veloura-muted hover:bg-veloura-card-hover hover:text-veloura-text',
                    )}
                  >
                    <span aria-hidden className="w-4 text-center">
                      {item.icon}
                    </span>
                    {item.title}
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
