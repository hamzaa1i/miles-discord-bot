import type { MetadataRoute } from 'next';

import { MODULE_DOCS } from '@/lib/docs-modules';
import { siteUrl } from '@/lib/marketing';

/**
 * app/sitemap.ts — PHASE M PART 9.
 *
 * Static sitemap for every PUBLIC route (auth-gated /servers and the
 * /api proxy are excluded by design).
 */

export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteUrl();
  const now = new Date();

  const pages: MetadataRoute.Sitemap = [
    { url: `${base}/`, lastModified: now, changeFrequency: 'weekly', priority: 1 },
    { url: `${base}/docs`, lastModified: now, changeFrequency: 'weekly', priority: 0.9 },
    { url: `${base}/docs/getting-started`, lastModified: now, changeFrequency: 'monthly', priority: 0.8 },
    { url: `${base}/docs/commands`, lastModified: now, changeFrequency: 'weekly', priority: 0.9 },
    { url: `${base}/docs/modules`, lastModified: now, changeFrequency: 'weekly', priority: 0.8 },
    { url: `${base}/docs/dashboard`, lastModified: now, changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/docs/faq`, lastModified: now, changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/docs/api`, lastModified: now, changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/stats`, lastModified: now, changeFrequency: 'hourly', priority: 0.6 },
    { url: `${base}/changelog`, lastModified: now, changeFrequency: 'weekly', priority: 0.7 },
  ];

  const modulePages: MetadataRoute.Sitemap = MODULE_DOCS.map((m) => ({
    url: `${base}/docs/modules/${m.slug}`,
    lastModified: now,
    changeFrequency: 'monthly',
    priority: 0.5,
  }));

  return [...pages, ...modulePages];
}
