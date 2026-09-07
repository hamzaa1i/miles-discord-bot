import { ChangelogClient } from '@/components/site/ChangelogClient';
import { pageMetadata } from '@/lib/seo';

/**
 * app/changelog/page.tsx — PHASE M PART 5 — the changelog page.
 *
 * Server wrapper (metadata) around the filterable client view; data
 * comes from the auto-generated lib/changelog-data.ts.
 */

export const metadata = pageMetadata({
  title: 'changelog',
  description:
    'every aurelia release, softly noted — features, fixes, improvements and breaking changes, filterable by category. rss at /changelog.rss.',
  path: '/changelog',
});

export default function ChangelogPage() {
  return <ChangelogClient />;
}
