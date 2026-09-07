import { NextRequest, NextResponse } from 'next/server';

/** POST /api/auth/logout — clear the session cookie. */

const TOKEN_COOKIE = 'aurelia_token';

export async function POST(req: NextRequest) {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(TOKEN_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: req.nextUrl.origin.startsWith('https'),
    maxAge: 0,
    path: '/',
  });
  return res;
}
