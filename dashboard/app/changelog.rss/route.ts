import { CHANGELOG } from '@/lib/changelog-data';
import { siteUrl } from '@/lib/marketing';

/**
 * app/changelog.rss/route.ts — PHASE M PART 5.
 *
 * Serves the release notes as RSS 2.0 at /changelog.rss from the same
 * generated dataset as the page (and the backend's /api/changelog).
 * Static payload, revalidated hourly — cheap for crawlers and readers.
 */

export const dynamic = 'force-static';
export const revalidate = 3600;

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export async function GET(): Promise<Response> {
  const base = siteUrl();
  const items = CHANGELOG.map((v) => {
    const parts: string[] = [];
    for (const label of ['feature', 'fix', 'improvement', 'breaking'] as const) {
      for (const entry of v.categories[label] ?? []) {
        parts.push(`[${label}] ${entry}`);
      }
    }
    const body = parts.map((p) => esc(p)).join('<br>') || 'release notes';
    const title = esc(`aurelia ${v.version} — ${v.date}`.trim());
    return `    <item>
      <title>${title}</title>
      <link>${base}/changelog</link>
      <guid isPermaLink="false">aurelia-${esc(v.version)}</guid>
      <description>${body}</description>
    </item>`;
  }).join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>aurelia changelog</title>
    <link>${base}/changelog</link>
    <description>release notes for aurelia — the soft, elegant discord bot ✦</description>
    <language>en</language>
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
