import { NextRequest, NextResponse } from 'next/server';

/**
 * app/api/proxy/[...path]/route.ts — same-origin bearer relay.
 *
 * The browser only ever talks to THIS origin. This handler:
 *   1. reads the httpOnly `aurelia_token` cookie (auto-attached,
 *      never readable by client JS),
 *   2. forwards the request to the Flask dashboard API on Render with
 *      Authorization + X-CSRF-Token headers,
 *   3. relays JSON + status back.
 *
 * Because the browser -> Next.js hop is same-origin, no CORS is needed
 * for the dashboard itself (Flask CORS stays locked to DASHBOARD_URL
 * for direct clients).
 */

const TOKEN_COOKIE = 'aurelia_token';

function apiBase(): string {
  return (
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8080'
  ).replace(/\/$/, '');
}

async function relay(req: NextRequest, path: string[]): Promise<Response> {
  const token = req.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: 'not logged in' }, { status: 401 });
  }

  const url = `${apiBase()}/api/${path.map(encodeURIComponent).join('/')}${req.nextUrl.search}`;

  const headers: HeadersInit = {
    Authorization: `Bearer ${token}`,
    'User-Agent': 'aurelia-dashboard-proxy',
  };
  const csrf = req.headers.get('X-CSRF-Token');
  if (csrf) headers['X-CSRF-Token'] = csrf;

  let body: string | undefined;
  if (req.method !== 'GET' && req.method !== 'DELETE') {
    body = await req.text();
    if (body) headers['Content-Type'] = 'application/json';
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body,
      cache: 'no-store',
    });
  } catch {
    return NextResponse.json(
      { error: 'could not reach the bot api — is it awake?' },
      { status: 502 },
    );
  }

  const text = await upstream.text();
  return new NextResponse(text || '{}', {
    status: upstream.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return relay(req, ctx.params.path);
}

export async function PATCH(req: NextRequest, ctx: { params: { path: string[] } }) {
  return relay(req, ctx.params.path);
}

export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return relay(req, ctx.params.path);
}

export async function DELETE(req: NextRequest, ctx: { params: { path: string[] } }) {
  return relay(req, ctx.params.path);
}
