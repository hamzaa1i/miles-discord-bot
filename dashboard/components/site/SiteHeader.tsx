'use client';

/**
 * components/site/SiteHeader.tsx — public site navigation.
 *
 * Sticky, translucent, veloura-styled. Shown on every public page
 * (landing, docs, stats, changelog). The "login" pill turns into
 * "dashboard" for users that already hold the aurelia_token cookie
 * (presence-only check — the token value is never read here).
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';
import { GITHUB_URL, SUPPORT_SERVER_URL } from '@/lib/marketing';

const NAV = [
  { href: '/#features', label: 'features' },
  { href: '/docs', label: 'docs' },
  { href: '/stats', label: 'stats' },
  { href: '/changelog', label: 'changelog' },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [hasToken, setHasToken] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setHasToken(document.cookie.split(';').some((c) => c.trim().startsWith('aurelia_token=')));
  }, [pathname]);

  const isDocs = pathname.startsWith('/docs');

  return (
    <header className="sticky top-0 z-40 border-b border-veloura-border/60 bg-veloura-navy/80 backdrop-blur-md">
      <nav
        aria-label="site navigation"
        className="mx-auto flex h-16 max-w-6xl items-center gap-2 px-4 sm:px-6"
      >
        <Link
          href="/"
          className="group flex items-center gap-2.5"
          aria-label="aurelia home"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/aurelia-logo.png"
            alt="aurelia logo — a soft pink four-pointed star"
            width={30}
            height={30}
            className="transition-transform duration-300 group-hover:scale-110 group-hover:rotate-12"
          />
          <span className="font-heading text-xl tracking-wide text-veloura-text">
            aurelia
          </span>
          <span className="twinkle hidden text-xs text-veloura-pink sm:inline" aria-hidden>
            ✦
          </span>
        </Link>

        <div className="ml-auto hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'rounded-[10px] px-3 py-2 text-sm text-veloura-muted transition-colors hover:bg-veloura-card-hover hover:text-veloura-text',
                (item.href === '/docs' && isDocs) && 'text-veloura-pink',
              )}
            >
              {item.label}
            </Link>
          ))}
          {SUPPORT_SERVER_URL && (
            <a
              href={SUPPORT_SERVER_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-[10px] px-3 py-2 text-sm text-veloura-muted transition-colors hover:bg-veloura-card-hover hover:text-veloura-text"
              aria-label="join the support server (opens in a new tab)"
            >
              support
            </a>
          )}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-[10px] px-3 py-2 text-sm text-veloura-muted transition-colors hover:bg-veloura-card-hover hover:text-veloura-text"
            aria-label="aurelia on github (opens in a new tab)"
          >
            github
          </a>
          <Link
            href={hasToken ? '/servers' : '/login'}
            className="veloura-button-primary ml-2 px-4 py-2 text-sm"
          >
            <Icon name={hasToken ? 'settings' : 'logout'} size={15} />
            {hasToken ? 'dashboard' : 'login'}
          </Link>
        </div>

        {/* mobile menu button */}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label="toggle navigation menu"
          className="ml-auto rounded-[10px] p-2 text-veloura-muted hover:bg-veloura-card-hover hover:text-veloura-text md:hidden"
        >
          <Icon name={open ? 'x' : 'hash'} size={20} />
        </button>
      </nav>

      {/* mobile drawer */}
      {open && (
        <div className="border-t border-veloura-border/60 bg-veloura-navy/95 px-4 pb-4 pt-2 md:hidden">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className="block rounded-[10px] px-3 py-2.5 text-sm text-veloura-muted hover:bg-veloura-card-hover hover:text-veloura-text"
            >
              {item.label}
            </Link>
          ))}
          {SUPPORT_SERVER_URL && (
            <a
              href={SUPPORT_SERVER_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="block rounded-[10px] px-3 py-2.5 text-sm text-veloura-muted hover:bg-veloura-card-hover hover:text-veloura-text"
            >
              support
            </a>
          )}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-[10px] px-3 py-2.5 text-sm text-veloura-muted hover:bg-veloura-card-hover hover:text-veloura-text"
          >
            github
          </a>
          <Link
            href={hasToken ? '/servers' : '/login'}
            onClick={() => setOpen(false)}
            className="veloura-button-primary mt-3 w-full"
          >
            <Icon name={hasToken ? 'settings' : 'logout'} size={15} />
            {hasToken ? 'dashboard' : 'login'}
          </Link>
        </div>
      )}
    </header>
  );
}
