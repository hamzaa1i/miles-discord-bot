'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { beginLogin, LoginStartError } from '@/lib/discord';

const DEV = process.env.NODE_ENV === 'development';

/**
 * Turn a LoginStartError into a message a human actually wants to read.
 * Only the truly unknown case falls back to the generic text.
 */
function friendlyError(e: unknown): string {
  if (e instanceof LoginStartError) {
    switch (e.message) {
      case 'discord integration not configured':
        return 'discord integration not configured ♡ — ask the bot owner to set NEXT_PUBLIC_DISCORD_CLIENT_ID';
      case 'server configuration incomplete':
        return 'server configuration incomplete — please contact the bot owner ♡';
      case 'network error':
        return `aurelia couldn't connect right now ♡ (error: ${e.detail || 'network'})`;
      default: {
        const detail = e.detail ? ` — ${e.detail}` : '';
        return `aurelia couldn't connect right now ♡ (error: ${e.message}${detail})`;
      }
    }
  }
  if (e instanceof Error && e.message) return `aurelia couldn't connect right now ♡ (error: ${e.message})`;
  return 'could not start login ♡';
}

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // already logged in? straight to servers
  useEffect(() => {
    fetch('/api/auth/session', { cache: 'no-store' })
      .then((r) => r.json())
      .then((body: { authenticated: boolean }) => {
        if (body.authenticated) router.replace('/servers');
      })
      .catch(() => {});
  }, [router]);

  async function login() {
    // the OAuth state round-trips through a cookie — without cookies the
    // flow can never complete, so check up front with a clear message
    if (typeof navigator !== 'undefined' && !navigator.cookieEnabled) {
      setError('cookies are disabled — aurelia needs them to remember you ♡');
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const { url, origin, warnings } = await beginLogin();

      if (DEV) {
        // eslint-disable-next-line no-console
        console.debug('[aurelia login] debug info', {
          nextauthUrl: origin,
          cookiesEnabled: navigator.cookieEnabled,
          warnings,
          authorizeUrl: url,
        });
      }

      window.location.href = url;
    } catch (e) {
      if (DEV) {
        // eslint-disable-next-line no-console
        console.error('[aurelia login] login could not start — full error object:', e);
      }
      setError(friendlyError(e));
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-6">
      <div className="pointer-events-none absolute -top-24 left-1/2 h-96 w-[560px] -translate-x-1/2 rounded-full bg-veloura-pink/10 blur-3xl" />

      <div className="veloura-card relative w-full max-w-md p-8 text-center animate-fade-in">
        <div className="mb-2 flex justify-center gap-3 text-veloura-lavender/70" aria-hidden>
          <span className="twinkle">✦</span>
          <span className="twinkle">✧</span>
          <span className="twinkle">✩</span>
        </div>
        <img src="/aurelia-logo.png" alt="" width={72} height={72} className="mx-auto mb-6" />
        <h1 className="font-heading text-3xl text-veloura-text">welcome back</h1>
        <p className="mt-3 text-sm leading-relaxed text-veloura-muted">
          sign in with discord to manage aurelia in the servers you keep.
          we only request <code className="rounded bg-veloura-navy px-1.5 py-0.5 text-veloura-lavender">identify</code> and{' '}
          <code className="rounded bg-veloura-navy px-1.5 py-0.5 text-veloura-lavender">guilds</code> — nothing more.
        </p>

        <button
          onClick={login}
          disabled={busy}
          className="veloura-button-primary mt-8 w-full text-base"
        >
          {busy ? 'opening the veil…' : '✦ continue with discord'}
        </button>

        {error && (
          <div className="mt-4 rounded-[12px] border border-veloura-danger/30 bg-veloura-danger/10 px-4 py-3">
            <p className="text-sm leading-relaxed text-veloura-danger">{error}</p>
            <button
              onClick={login}
              disabled={busy}
              className="veloura-button-ghost mt-3 w-full text-sm"
            >
              ✧ try again
            </button>
          </div>
        )}

        <p className="mt-6 text-xs text-veloura-muted/60">
          the token is stored in an httpOnly cookie and never touches localStorage.
        </p>
      </div>
    </div>
  );
}
