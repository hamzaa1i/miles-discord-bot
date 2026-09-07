'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { GuildIcon } from '@/components/GuildIcon';
import { Card, LoadingCard, ErrorCard, Badge } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import { nf, timeAgo } from '@/lib/format';
import { defaultAvatar } from '@/lib/discord';

export default function ServersPage() {
  const { user, guilds, loading, error, logout } = useAuth();
  const toast = useToast();

  if (loading) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="mb-6 font-heading text-3xl">your servers</h1>
        <div className="grid gap-4 sm:grid-cols-2">
          <LoadingCard label="fetching your servers…" />
          <LoadingCard />
        </div>
      </main>
    );
  }

  if (error === 'not logged in') {
    return (
      <main className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-6 text-center">
        <img src="/aurelia-logo.png" alt="" width={72} height={72} className="mb-6" />
        <h1 className="font-heading text-3xl">drifting away…</h1>
        <p className="mt-3 text-sm text-veloura-muted">your session expired — sign in again</p>
        <Link href="/login" className="veloura-button-primary mt-6">
          ✦ login with discord
        </Link>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <ErrorCard message={error} />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12 animate-fade-in">
      {/* header */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl text-veloura-text">your servers</h1>
          <p className="mt-2 text-sm text-veloura-muted">
            servers where you have <span className="text-veloura-pink">manage server</span> and
            aurelia is present
          </p>
        </div>
        {user && (
          <div className="flex items-center gap-3">
            <img
              src={user.avatar ?? defaultAvatar(user.id)}
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 rounded-full border border-veloura-border"
            />
            <div className="hidden sm:block">
              <p className="text-sm font-medium text-veloura-text">{user.display_name}</p>
              <button
                onClick={() => {
                  void logout();
                  toast.push('signed out ✧', 'info');
                }}
                className="text-xs text-veloura-muted transition hover:text-veloura-danger"
              >
                sign out
              </button>
            </div>
          </div>
        )}
      </div>

      {/* grid */}
      {guilds && guilds.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {guilds.map((g) => (
            <Card
              key={g.id}
              className="group flex flex-col gap-4 transition hover:border-veloura-pink/40 hover:shadow-glow"
            >
              <div className="flex items-center gap-4">
                <GuildIcon id={g.id} name={g.name} icon={g.icon} size={56} />
                <div className="min-w-0 flex-1">
                  <h2 className="truncate font-heading text-lg text-veloura-text">{g.name}</h2>
                  <div className="mt-1.5 flex flex-wrap gap-2">
                    <Badge tone="muted">{nf(g.member_count)} members</Badge>
                    {g.owner && <Badge tone="pink">owner</Badge>}
                  </div>
                </div>
              </div>
              <Link
                href={`/servers/${g.id}`}
                className="veloura-button-primary w-full group-hover:shadow-glow"
              >
                ✦ manage
              </Link>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="text-center">
          <p className="text-3xl" aria-hidden>
            🌙
          </p>
          <p className="mt-3 text-sm text-veloura-muted">
            no manageable servers with aurelia yet
          </p>
          <p className="mt-1.5 text-xs text-veloura-muted/60">
            invite aurelia to a server where you manage, then refresh
          </p>
          <a
            href={`https://discord.com/oauth2/authorize?client_id=${process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID ?? ''}&permissions=8&scope=bot%20applications.commands`}
            target="_blank"
            rel="noreferrer"
            className="veloura-button-ghost mt-5"
          >
            invite aurelia ✧
          </a>
        </Card>
      )}

      <footer className="mt-12 text-center text-xs text-veloura-muted/50">
        last refreshed {timeAgo(new Date().toISOString())} · ✦ wrapped in veloura
      </footer>
    </main>
  );
}
