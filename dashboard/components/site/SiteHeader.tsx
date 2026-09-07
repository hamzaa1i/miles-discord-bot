'use client';

/**
 * components/site/SiteHeader.tsx — public site navigation.
 *
 * PHASE N (19.1) — auth-aware header. The old cookie-presence probe
 * ("aurelia_token= exists") stayed stuck on "dashboard" after a session
 * expired, and never showed who was signed in. The header now uses the
 * AuthProvider session (backed by the same-origin httpOnly-cookie proxy
 * — the Discord token is never readable here, only the user object):
 *
 *   logged out  → "login" pill
 *   logged in   → avatar + display name + dropdown:
 *                 dashboard · my servers · sign out
 *
 * The public repo link was removed for private-source preparation; the
 * footer keeps a creator-profile attribution link instead.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';
import { defaultAvatar } from '@/lib/discord';
import { SUPPORT_SERVER_URL } from '@/lib/marketing';
import { useAuth } from '@/lib/auth';

const NAV = [
  { href: '/#features', label: 'features' },
  { href: '/docs', label: 'docs' },
  { href: '/stats', label: 'stats' },
  { href: '/changelog', label: 'changelog' },
];

function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onEsc);
    };
  }, [open]);

  if (!user) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="open your profile menu"
        className="flex items-center gap-2 rounded-[10px] border border-veloura-border/70 py-1 pl-1 pr-2.5 transition hover:border-veloura-pink/40 hover:bg-veloura-card-hover"
      >
        <img
          src={user.avatar ?? defaultAvatar(user.id)}
          alt={`${user.display_name} avatar`}
          width={26}
          height={26}
          className="h-[26px] w-[26px] rounded-full"
        />
        <span className="hidden max-w-[140px] truncate text-sm text-veloura-text sm:inline">
          {user.display_name}
        </span>
        <span
          aria-hidden
          className={cn('text-[10px] text-veloura-muted transition-transform', open && 'rotate-180')}
        >
          ▾
        </span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-44 rounded-[12px] border border-veloura-border bg-veloura-navy-deep p-1.5 shadow-soft"
        >
          <Link
            role="menuitem"
            href="/servers"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 rounded-[9px] px-3 py-2 text-sm text-veloura-muted transition hover:bg-veloura-card-hover hover:text-veloura-text"
          >
            <Icon name="settings" size={14} />
            dashboard
          </Link>
          <Link
            role="menuitem"
            href="/servers"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 rounded-[9px] px-3 py-2 text-sm text-veloura-muted transition hover:bg-veloura-card-hover hover:text-veloura-text"
          >
            <Icon name="hash" size={14} />
            my servers
          </Link>
          <button
            role="menuitem"
            type="button"
            onClick={() => {
              setOpen(false);
              void logout();
            }}
            className="flex w-full items-center gap-2.5 rounded-[9px] px-3 py-2 text-left text-sm text-veloura-muted transition hover:bg-veloura-card-hover hover:text-veloura-danger"
          >
            <Icon name="logout" size={14} />
            sign out
          </button>
        </div>
      )}
    </div>
  );
}

function AuthButton() {
  const { user, loading } = useAuth();

  // While the session probe runs, render a neutral placeholder that
  // matches the login pill's footprint — no login→profile flash.
  if (loading) {
    return <span className="veloura-button-primary ml-2 px-4 py-2 text-sm opacity-70">✦</span>;
  }

  if (user) return <ProfileMenu />;

  return (
    <Link href="/login" className="veloura-button-primary ml-2 px-4 py-2 text-sm">
      <Icon name="logout" size={15} />
      login
    </Link>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // close the mobile drawer on navigation
  useEffect(() => {
    setOpen(false);
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
          <AuthButton />
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

      {/* mobile drawer — same essential destinations as desktop */}
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
          <div className="mt-3">
            <MobileAuthButton />
          </div>
        </div>
      )}
    </header>
  );
}

function MobileAuthButton() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return <span className="veloura-button-primary w-full py-2.5 text-center opacity-70">✦</span>;
  }

  if (user) {
    return (
      <div className="veloura-card !p-2">
        <div className="flex items-center gap-2.5 px-2 py-1.5">
          <img
            src={user.avatar ?? defaultAvatar(user.id)}
            alt={`${user.display_name} avatar`}
            width={28}
            height={28}
            className="h-7 w-7 rounded-full"
          />
          <span className="truncate text-sm text-veloura-text">{user.display_name}</span>
        </div>
        <Link
          href="/servers"
          className="veloura-button-primary mt-1 w-full !py-2 text-sm"
        >
          <Icon name="settings" size={14} />
          open dashboard
        </Link>
        <button
          type="button"
          onClick={() => void logout()}
          className="mt-1 w-full rounded-[12px] px-3 py-2 text-sm text-veloura-muted transition hover:text-veloura-danger"
        >
          sign out
        </button>
      </div>
    );
  }

  return (
    <Link href="/login" className="veloura-button-primary w-full">
      <Icon name="logout" size={15} />
      login
    </Link>
  );
}
