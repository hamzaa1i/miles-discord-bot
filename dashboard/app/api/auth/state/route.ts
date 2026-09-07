import { NextRequest, NextResponse } from 'next/server';

/**
 * GET /api/auth/state — start the OAuth flow.
 *
 * Generates a CSRF `state`, stores it in a short-lived httpOnly cookie
 * (verified by /api/auth/exchange), and returns the fully-built Discord
 * authorize URL (scopes: identify + guilds).
 *
 * Error handling: every failure returns a JSON body with a stable `error`
 * code + human-readable `detail`, so the login page can show the ACTUAL
 * reason instead of a generic "could not start login":
 *   - 500 "discord integration not configured"   → client id env missing
 *   - 500 "server configuration incomplete"       → no usable origin in prod
 *
 * The success body also carries `origin` (the effective NEXTAUTH_URL /
 * request origin used to build redirect_uri) and `warnings` (config
 * mismatches worth logging in dev), so the client can debug cookie and
 * domain issues without server access.
 */

const STATE_COOKIE = 'aurelia_oauth_state';

function explicitOrigin(): string {
  return (process.env.NEXTAUTH_URL || '').replace(/\/$/, '');
}

function requestOrigin(req: NextRequest): string {
  return (
    process.env.APP_URL ||
    req.nextUrl.origin ||
    'http://localhost:3000'
  ).replace(/\/$/, '');
}

function isLocalOrigin(origin: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
}

export async function GET(req: NextRequest) {
  const clientId = process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID || process.env.DISCORD_CLIENT_ID;

  // explicit check 1 — the Discord application id
  if (!clientId) {
    return NextResponse.json(
      {
        error: 'discord integration not configured',
        detail:
          'NEXT_PUBLIC_DISCORD_CLIENT_ID (or DISCORD_CLIENT_ID) is not set in the environment — set it in Vercel project settings',
      },
      { status: 500 },
    );
  }

  const declared = explicitOrigin();
  const fallback = requestOrigin(req);
  const origin = declared || fallback;

  // explicit check 2 — a usable redirect origin.
  // NEXTAUTH_URL is preferred; the request origin is a working fallback on
  // Vercel. Only hard-fail when production somehow resolves to localhost.
  if (!declared && process.env.NODE_ENV === 'production' && isLocalOrigin(origin)) {
    return NextResponse.json(
      {
        error: 'server configuration incomplete',
        detail: 'NEXTAUTH_URL is not set and no public origin could be derived — please contact the bot owner',
      },
      { status: 500 },
    );
  }

  // diagnostics (surfaced to the login page's dev console)
  const warnings: string[] = [];
  if (!declared) {
    warnings.push(`NEXTAUTH_URL not set — using request origin (${origin})`);
  } else if (declared !== fallback) {
    warnings.push(
      `NEXTAUTH_URL (${declared}) differs from the origin actually serving this page (${fallback}) — make sure the Discord OAuth redirect matches`,
    );
  }

  const state = crypto.randomUUID().replaceAll('-', '');

  const url = new URL('https://discord.com/oauth2/authorize');
  url.searchParams.set('client_id', clientId);
  url.searchParams.set('redirect_uri', `${origin}/oauth/callback`);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('scope', 'identify guilds');
  url.searchParams.set('state', state);
  url.searchParams.set('prompt', 'consent');

  const res = NextResponse.json({ url: url.toString(), state, origin, warnings });
  res.cookies.set(STATE_COOKIE, state, {
    httpOnly: true,
    sameSite: 'lax',
    secure: origin.startsWith('https'),
    maxAge: 600, // 10 minutes
    path: '/',
  });
  return res;
}
