'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function CallbackInner() {
  const router = useRouter();
  void router; // navigation happens via window.location.assign (see finish)
  const params = useSearchParams();
  const [status, setStatus] = useState<'working' | 'settling' | 'error'>('working');
  const [error, setError] = useState<string | null>(null);

  const finish = useCallback(() => {
    // Full page navigation (NOT router.replace): the AuthProvider in the
    // root layout mounted BEFORE the cookie existed and cached its
    // "not logged in" state — a client-side route change would render
    // /servers against that stale state ("drifting away"). A real
    // navigation remounts the app with the fresh httpOnly cookie.
    window.history.replaceState(null, '', window.location.pathname);
    setStatus('settling');
    window.location.assign('/servers');
  }, []);

  useEffect(() => {
    const code = params.get('code');
    const oauthError = params.get('error');
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const fragmentToken = fragment.get('token');

    (async () => {
      try {
        if (oauthError) throw new Error(oauthError);

        // Flow A (primary): Next.js exchange route
        if (code) {
          const res = await fetch('/api/auth/exchange', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, state: params.get('state') }),
          });
          if (!res.ok) {
            const body = (await res.json().catch(() => null)) as { error?: string } | null;
            throw new Error(body?.error ?? `exchange failed (${res.status})`);
          }
          finish();
          return;
        }

        // Flow B (alternative): Flask /api/dashboard/oauth/callback put the
        // token in the URL fragment — copy it into the httpOnly cookie.
        if (fragmentToken) {
          const res = await fetch('/api/auth/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: fragmentToken }),
          });
          if (!res.ok) throw new Error('could not store the session token');
          finish();
          return;
        }

        throw new Error('no code or token found in the callback url');
      } catch (e) {
        setError(e instanceof Error ? e.message : 'oauth failed');
        setStatus('error');
      }
    })();
  }, [params, finish]);

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="veloura-card w-full max-w-md p-8 text-center animate-fade-in">
        <img src="/aurelia-logo.png" alt="" width={64} height={64} className="mx-auto mb-6" />
        {status === 'working' ? (
          <>
            <h1 className="font-heading text-2xl">binding the stars…</h1>
            <div className="mx-auto mt-6 h-1 w-40 overflow-hidden rounded-full bg-veloura-border">
              <div className="h-full w-1/2 animate-pulse-soft rounded-full bg-veloura-pink" />
            </div>
            <p className="mt-4 text-sm text-veloura-muted">exchanging your discord token</p>
          </>
        ) : status === 'settling' ? (
          <>
            <h1 className="font-heading text-2xl">settling in…</h1>
            <div className="mx-auto mt-6 h-1 w-40 overflow-hidden rounded-full bg-veloura-border">
              <div className="h-full w-1/2 animate-pulse-soft rounded-full bg-veloura-lavender" />
            </div>
            <p className="mt-4 text-sm text-veloura-muted">finding your servers</p>
          </>
        ) : (
          <>
            <h1 className="font-heading text-2xl text-veloura-danger">the stars misaligned</h1>
            <p className="mt-3 text-sm text-veloura-muted">{error}</p>
            <a href="/login" className="veloura-button-ghost mt-6 w-full">
              try again
            </a>
          </>
        )}
      </div>
    </div>
  );
}

export default function OauthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-veloura-muted">loading…</p>
        </div>
      }
    >
      <CallbackInner />
    </Suspense>
  );
}
