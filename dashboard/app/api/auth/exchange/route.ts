import { NextRequest, NextResponse } from 'next/server';

/**
 * POST /api/auth/exchange — swap the OAuth code for an access token.
 *
 * 1. verifies the CSRF state against the cookie set by /api/auth/state
 * 2. exchanges the code with Discord using DISCORD_CLIENT_SECRET
 *    (server-side env — never exposed to the browser)
 * 3. stores the access token in an httpOnly `aurelia_token` cookie
 */

const STATE_COOKIE = 'aurelia_oauth_state';
const TOKEN_COOKIE = 'aurelia_token';
const TOKEN_TTL = 7 * 24 * 3600; // Discord user access tokens live ~7 days

function appOrigin(req: NextRequest): string {
  return (
    process.env.NEXTAUTH_URL ||
    process.env.APP_URL ||
    req.nextUrl.origin ||
    'http://localhost:3000'
  ).replace(/\/$/, '');
}

export async function POST(req: NextRequest) {
  const clientId = process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID || process.env.DISCORD_CLIENT_ID;
  const clientSecret = process.env.DISCORD_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    return NextResponse.json(
      { error: 'discord oauth is not configured (DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET)' },
      { status: 500 },
    );
  }

  let body: { code?: string; state?: string };
  try {
    body = (await req.json()) as { code?: string; state?: string };
  } catch {
    return NextResponse.json({ error: 'invalid json body' }, { status: 400 });
  }

  const code = (body.code ?? '').trim();
  const state = (body.state ?? '').trim();
  if (!code) return NextResponse.json({ error: 'missing code' }, { status: 400 });

  // CSRF: state must match the cookie from /api/auth/state
  const cookieState = req.cookies.get(STATE_COOKIE)?.value;
  if (!cookieState || !state || cookieState !== state) {
    return NextResponse.json({ error: 'state mismatch — restart the login flow' }, { status: 403 });
  }

  const origin = appOrigin(req);
  const redirectUri = `${origin}/oauth/callback`;

  const form = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri,
  });

  let tokenData: { access_token?: string; expires_in?: number; scope?: string };
  try {
    const res = await fetch('https://discord.com/api/v10/oauth2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `discord rejected the code (${res.status})` },
        { status: 400 },
      );
    }
    tokenData = (await res.json()) as typeof tokenData;
  } catch {
    return NextResponse.json({ error: 'could not reach discord' }, { status: 502 });
  }

  const token = tokenData.access_token;
  if (!token) return NextResponse.json({ error: 'no access token in response' }, { status: 502 });

  const res = NextResponse.json({ ok: true, scope: tokenData.scope ?? 'identify guilds' });
  res.cookies.set(TOKEN_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: origin.startsWith('https'),
    maxAge: Math.min(tokenData.expires_in ?? TOKEN_TTL, TOKEN_TTL),
    path: '/',
  });
  res.cookies.delete(STATE_COOKIE);
  return res;
}
