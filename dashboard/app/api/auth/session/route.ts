import { NextRequest, NextResponse } from 'next/server';

/**
 * /api/auth/session
 *
 *  GET  — is there a token cookie? (lightweight auth probe)
 *  POST — { token } : adopt a token obtained via the Flask OAuth
 *         callback flow (#token= fragment) into the httpOnly cookie.
 */

const TOKEN_COOKIE = 'aurelia_token';
const TOKEN_TTL = 7 * 24 * 3600;

function origin(req: NextRequest): string {
  return (
    process.env.NEXTAUTH_URL ||
    process.env.APP_URL ||
    req.nextUrl.origin ||
    'http://localhost:3000'
  ).replace(/\/$/, '');
}

export async function GET(req: NextRequest) {
  return NextResponse.json({
    authenticated: Boolean(req.cookies.get(TOKEN_COOKIE)?.value),
  });
}

export async function POST(req: NextRequest) {
  let body: { token?: string };
  try {
    body = (await req.json()) as { token?: string };
  } catch {
    return NextResponse.json({ error: 'invalid json body' }, { status: 400 });
  }
  const token = (body.token ?? '').trim();
  if (!token || token.length < 20 || token.length > 512) {
    return NextResponse.json({ error: 'invalid token' }, { status: 400 });
  }

  // Verify the token is real before storing it — never cookie garbage.
  try {
    const res = await fetch('https://discord.com/api/v10/users/@me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      return NextResponse.json({ error: 'discord rejected this token' }, { status: 401 });
    }
  } catch {
    return NextResponse.json({ error: 'could not reach discord' }, { status: 502 });
  }

  const o = origin(req);
  const out = NextResponse.json({ ok: true });
  out.cookies.set(TOKEN_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: o.startsWith('https'),
    maxAge: TOKEN_TTL,
    path: '/',
  });
  return out;
}
