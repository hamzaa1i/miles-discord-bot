import { NextRequest, NextResponse } from 'next/server';

/**
 * middleware.ts — lightweight route guard.
 *
 * /servers/* requires the aurelia_token cookie; /login redirects to
 * /servers when already authenticated. The cookie VALUE is never
 * inspected here — only its presence (the token itself is only read
 * server-side by the proxy route handlers).
 */

const TOKEN_COOKIE = 'aurelia_token';

export function middleware(req: NextRequest) {
  const hasToken = Boolean(req.cookies.get(TOKEN_COOKIE)?.value);
  const { pathname } = req.nextUrl;

  if (pathname.startsWith('/servers') && !hasToken) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.search = '';
    return NextResponse.redirect(url);
  }

  if (pathname === '/login' && hasToken) {
    const url = req.nextUrl.clone();
    url.pathname = '/servers';
    url.search = '';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/servers/:path*', '/login'],
};
