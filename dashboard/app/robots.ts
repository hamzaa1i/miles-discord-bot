import type { MetadataRoute } from 'next';

import { siteUrl } from '@/lib/marketing';

/**
 * app/robots.ts — PHASE M PART 9.
 *
 * All public marketing/docs routes are crawlable. The authenticated
 * dashboard (/servers/*) and the internal proxy (/api/*) are excluded.
 */

export default function robots(): MetadataRoute.Robots {
  const base = siteUrl();
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/servers', '/api/', '/oauth/'],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
