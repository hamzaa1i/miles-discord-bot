'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { beginLogin } from '@/lib/discord';

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
    setBusy(true);
    setError(null);
    try {
      const { url } = await beginLogin();
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'could not start the login flow');
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
          <p className="mt-4 rounded-[12px] border border-veloura-danger/30 bg-veloura-danger/10 px-4 py-3 text-sm text-veloura-danger">
            {error}
          </p>
        )}

        <p className="mt-6 text-xs text-veloura-muted/60">
          the token is stored in an httpOnly cookie and never touches localStorage.
        </p>
      </div>
    </div>
  );
}
