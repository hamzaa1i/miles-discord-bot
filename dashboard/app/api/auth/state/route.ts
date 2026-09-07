import { NextRequest, NextResponse } from 'next/server';

/**
 * GET /api/auth/state — start the OAuth flow.
 *
 * Generates a CSRF `state`, stores it in a short-lived httpOnly cookie
 * (verified by /api/auth/exchange), and returns the fully-built Discord
 * authorize URL (scopes: identify + guilds).
 */

const STATE_COOKIE = 'aurelia_oauth_state';

function appOrigin(req: NextRequest): string {
  return (
    process.env.NEXTAUTH_URL ||
    process.env.APP_URL ||
    req.nextUrl.origin ||
    'http://localhost:3000'
  ).replace(/\/$/, '');
}

export async function GET(req: NextRequest) {
  const clientId = process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID || process.env.DISCORD_CLIENT_ID;
  if (!clientId) {
    return NextResponse.json(
      { error: 'NEXT_PUBLIC_DISCORD_CLIENT_ID is not configured' },
      { status: 500 },
    );
  }

  const state = crypto.randomUUID().replaceAll('-', '');
  const origin = appOrigin(req);
  const redirectUri = `${origin}/oauth/callback`;

  const url = new URL('https://discord.com/oauth2/authorize');
  url.searchParams.set('client_id', clientId);
  url.searchParams.set('redirect_uri', redirectUri);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('scope', 'identify guilds');
  url.searchParams.set('state', state);
  url.searchParams.set('prompt', 'consent');

  const res = NextResponse.json({ url: url.toString(), state });
  res.cookies.set(STATE_COOKIE, state, {
    httpOnly: true,
    sameSite: 'lax',
    secure: origin.startsWith('https'),
    maxAge: 600, // 10 minutes
    path: '/',
  });
  return res;
}
