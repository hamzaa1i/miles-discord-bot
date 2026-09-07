'use client';

/**
 * app/servers/[guildId]/layout.tsx — guild shell:
 * GuildProvider (overview + resources + audit) + sidebar + mobile drawer.
 */

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { GuildProvider, useGuild } from '@/lib/guild';
import { useAuth } from '@/lib/auth';
import { Sidebar } from '@/components/Sidebar';
import { GuildIcon } from '@/components/GuildIcon';
import { defaultAvatar } from '@/lib/discord';
import { cn } from '@/lib/format';
import { X } from 'lucide-react';

function Shell({ guildId, children }: { guildId: string; children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { overview, loading, error } = useGuild();
  const { user, logout } = useAuth();

  return (
    <div className="relative flex min-h-screen">
      {/* ambient glow */}
      <div className="pointer-events-none fixed -top-40 left-1/4 h-96 w-96 rounded-full bg-veloura-pink/5 blur-3xl" />

      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-veloura-border/60 bg-veloura-navy-deep/60 lg:block">
        <Link
          href="/servers"
          className="flex items-center gap-3 border-b border-veloura-border/60 px-5 py-4 transition hover:bg-veloura-card-hover/40"
        >
          <GuildIcon
            id={guildId}
            name={overview?.name ?? '…'}
            icon={overview?.icon ?? null}
            size={36}
          />
          <div className="min-w-0">
            <p className="truncate font-heading text-base text-veloura-text">
              {overview?.name ?? 'loading…'}
            </p>
            <p className="text-[11px] text-veloura-muted/70">← all servers</p>
          </div>
        </Link>
        <div className="h-[calc(100vh-69px)]">
          <Sidebar guildId={guildId} />
        </div>
      </aside>

      {/* mobile drawer */}
      <div
        className={cn(
          'fixed inset-0 z-40 lg:hidden',
          drawerOpen ? 'pointer-events-auto' : 'pointer-events-none',
        )}
        aria-hidden={!drawerOpen}
      >
        <div
          className={cn('absolute inset-0 bg-black/60 transition-opacity', drawerOpen ? 'opacity-100' : 'opacity-0')}
          onClick={() => setDrawerOpen(false)}
        />
        <div
          className={cn(
            'absolute left-0 top-0 h-full w-72 border-r border-veloura-border bg-veloura-navy-deep transition-transform duration-200',
            drawerOpen ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          <div className="flex items-center justify-between border-b border-veloura-border/60 px-4 py-3">
            <Link href="/servers" onClick={() => setDrawerOpen(false)} className="flex items-center gap-2">
              <GuildIcon id={guildId} name={overview?.name ?? '…'} icon={overview?.icon ?? null} size={32} />
              <span className="truncate font-heading text-sm">{overview?.name ?? '…'}</span>
            </Link>
            <button
              onClick={() => setDrawerOpen(false)}
              aria-label="close navigation"
              className="rounded-[10px] p-2 text-veloura-muted hover:text-veloura-text"
            >
              <X size={16} strokeWidth={2} />
            </button>
          </div>
          <div className="h-[calc(100%-57px)]">
            <Sidebar guildId={guildId} onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      </div>

      {/* main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* top bar */}
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-veloura-border/60 bg-veloura-navy/95 px-4 py-3 backdrop-blur sm:px-6">
          <button
            onClick={() => setDrawerOpen(true)}
            aria-label="open navigation"
            className="rounded-[10px] border border-veloura-border p-2 text-veloura-muted transition hover:text-veloura-text lg:hidden"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <path d="M2 4h14M2 9h14M2 14h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate font-heading text-base text-veloura-text">
              {loading ? '…' : overview?.name ?? 'server'}
            </p>
            {!loading && !error && overview && (
              <p className="text-[11px] text-veloura-muted/70">
                {overview.member_count?.toLocaleString() ?? '—'} members ·{' '}
                {overview.boost_count > 0 ? `${overview.boost_count} boosts · ` : ''}aurelia ✦
              </p>
            )}
            {error && <p className="text-[11px] text-veloura-danger">{error}</p>}
          </div>
          {user && (
            <img
              src={user.avatar ?? defaultAvatar(user.id)}
              alt={`${user.display_name} avatar`}
              width={34}
              height={34}
              className="h-[34px] w-[34px] rounded-full border border-veloura-border"
            />
          )}
          <button
            onClick={() => void logout()}
            className="veloura-button-ghost !min-h-[36px] px-3 text-xs"
            title="sign out"
          >
            sign out
          </button>
        </header>

        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}

export default function GuildLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ guildId: string }>();
  const guildId = String(params?.guildId ?? '');

  return (
    <GuildProvider guildId={guildId}>
      <Shell guildId={guildId}>{children}</Shell>
    </GuildProvider>
  );
}
