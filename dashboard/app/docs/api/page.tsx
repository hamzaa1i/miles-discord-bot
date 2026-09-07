import Link from 'next/link';
import { DocsBreadcrumb } from '@/components/docs/DocsBreadcrumb';

import { CodeBlock } from '@/components/docs/CodeBlock';
import { ShareButtons } from '@/components/site/ShareButtons';
import { siteUrl } from '@/lib/marketing';
import { pageMetadata } from '@/lib/seo';

/**
 * app/docs/api/page.tsx — developer-facing api docs.
 *
 * Documents the PUBLIC endpoints (stats, changelog, rss — no auth) and
 * explains the auth model for the private dashboard api (bearer +
 * csrf), without exposing anything sensitive. The live examples use
 * the deployed backend URL from env.
 */

export const metadata = pageMetadata({
  title: 'api',
  description:
    'public aurelia endpoints for developers — live stats, changelog and rss — plus how the dashboard api authenticates.',
  path: '/docs/api',
});

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'https://miles-discord-bot.onrender.com').replace(/\/$/, '');

export default function ApiDocs() {
  return (
    <>
      <DocsBreadcrumb page="api" />

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">for developers</p>
        <h1 className="font-heading mt-2 text-4xl text-veloura-text">the api ✦</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
          a small, deliberate surface: two public read-only endpoints (plus
          an rss feed) for status pages and bots, and the authenticated
          dashboard api that powers this site.
        </p>
      </header>

      <section aria-label="public endpoints">
        <h2 className="font-heading text-2xl text-veloura-text">public endpoints</h2>
        <p className="mt-2 text-sm leading-relaxed text-veloura-muted">
          no authentication. aggregated and anonymized only — command names
          and counts, never user or guild ids. rate limited to 60
          requests/minute per ip and cached for 60 seconds on the server.
        </p>

        <div className="mt-6 space-y-6">
          <div>
            <h3 className="font-mono text-sm text-veloura-pink">GET /api/public/stats</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">
              live vitals (servers, members, latency, uptime), today&apos;s
              command usage, top commands (7 days), fun aggregate counters
              (total xp, warnings, confessions, memories, active streaks),
              a growth series and a latency history for charts.
            </p>
            <CodeBlock title="request">{`curl ${API_BASE}/api/public/stats`}</CodeBlock>
            <CodeBlock title="response (trimmed)">{`{
  "status": "ok",
  "version": "1.1.0",
  "servers": 5,
  "members": 1234,
  "latency_ms": 82.5,
  "uptime_seconds": 432000,
  "uptime_percent": 99.87,
  "commands_used_today": 214,
  "top_commands": [{ "command": "daily", "count": 41 }],
  "fun_stats": {
    "total_xp": 812345,
    "warnings_issued": 37,
    "confessions_posted": 12,
    "memories_stored": 214,
    "daily_streaks_active": 18
  },
  "growth": [{ "date": "2026-09-01", "servers": 3 }]
}`}</CodeBlock>
          </div>

          <div>
            <h3 className="font-mono text-sm text-veloura-pink">GET /api/changelog</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">
              the parsed release notes — a json array of versions with
              feature / fix / improvement / breaking categories. mirrors{' '}
              <Link href="/changelog" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
                /changelog
              </Link>
              .
            </p>
            <CodeBlock title="request">{`curl ${API_BASE}/api/changelog`}</CodeBlock>
          </div>

          <div>
            <h3 className="font-mono text-sm text-veloura-pink">GET /changelog.rss</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">
              the same releases as rss 2.0 — subscribe from any reader.
            </p>
            <CodeBlock title="request">{`curl ${API_BASE}/changelog.rss`}</CodeBlock>
          </div>

          <div>
            <h3 className="font-mono text-sm text-veloura-pink">GET /health</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">
              plain vitals (status, uptime, guilds, users, latency,
              supabase flag) — what the landing page stats bar polls.
            </p>
            <CodeBlock title="request">{`curl ${API_BASE}/health`}</CodeBlock>
          </div>
        </div>
      </section>

      <section aria-label="dashboard api" className="mt-12">
        <h2 className="font-heading text-2xl text-veloura-text">the dashboard api</h2>
        <p className="mt-2 text-sm leading-relaxed text-veloura-muted">
          the private half (settings reads/writes, live actions) is not a
          public api by design. requests must carry a discord oauth bearer
          token, the target guild must contain aurelia, the caller must
          hold manage server there, and mutations additionally need a
          csrf token bound to the bearer. everything is rate limited and
          audit logged.
        </p>
        <CodeBlock title="auth model">{`browser ──cookie──▶ next.js proxy ──bearer+csrf──▶ flask api
                (httpOnly)              (server-side only)

GET    /api/dashboard/guild/<gid>/settings/<module>
PATCH  /api/dashboard/guild/<gid>/settings/<module>
POST   /api/dashboard/guild/<gid>/action/<action>
GET    /api/dashboard/ai/status`}</CodeBlock>
        <p className="mt-2 text-sm leading-relaxed text-veloura-muted">
          curious how it all fits together? aurelia is a managed project
          with a privately maintained source — the{' '}
          <Link href="/stats" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            live stats page
          </Link>{' '}
          and the{' '}
          <Link href="/servers" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            dashboard itself
          </Link>{' '}
          are the living demonstration; questions about the topology are
          welcome in the support server.
        </p>
      </section>

      <section aria-label="fair use" className="mt-12">
        <h2 className="font-heading text-2xl text-veloura-text">fair use</h2>
        <ul className="mt-3 space-y-2">
          {[
            'poll the public endpoints at most once a minute — they are cached server-side anyway',
            'don’t scrape the authenticated api; log in like the dashboard does',
            'status pages and discord bots embedding her stats are explicitly welcome — link back to ' + siteUrl(),
          ].map((line) => (
            <li key={line} className="flex gap-2 text-sm leading-relaxed text-veloura-muted">
              <span className="mt-0.5 text-veloura-pink" aria-hidden>✦</span>
              {line}
            </li>
          ))}
        </ul>
      </section>

      <ShareButtons compact className="mt-10 no-print" text="aurelia’s public api — live stats for your status page ✦" />
    </>
  );
}
