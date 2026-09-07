import { StatsClient } from '@/components/site/StatsClient';
import { pageMetadata } from '@/lib/seo';

/**
 * app/stats/page.tsx — PHASE M PART 4 — public stats page.
 *
 * Server wrapper (metadata) around the live-polling client component.
 * No login required; the data comes from the public api.
 */

export const metadata = pageMetadata({
  title: 'stats',
  description:
    'live aurelia statistics — servers, members, command usage, uptime and the fun counters. anonymized and public.',
  path: '/stats',
});

export default function StatsPage() {
  return <StatsClient />;
}
