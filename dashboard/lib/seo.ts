/**
 * lib/seo.ts — shared metadata builder for public pages (PHASE M PART 9).
 *
 * One helper, every public page: Open Graph + Twitter cards + canonical
 * url + keywords. JSON-LD is emitted per-page (landing uses
 * SoftwareApplication, docs/articles use WebSite/WebPage).
 */

import type { Metadata } from 'next';
import {
  SITE_DESCRIPTION,
  SITE_KEYWORDS,
  SITE_NAME,
  SITE_TAGLINE,
  siteUrl,
} from '@/lib/marketing';

interface PageMeta {
  title: string;
  description: string;
  /** route path, e.g. '/docs/commands' */
  path: string;
  keywords?: string[];
  /** og image; defaults to the shared 1200×630 banner */
  image?: string;
}

export const OG_IMAGE = '/og-image.png';

export function pageMetadata({
  title,
  description,
  path,
  keywords,
  image = OG_IMAGE,
}: PageMeta): Metadata {
  const url = `${siteUrl()}${path}`;
  const fullTitle = path === '/' ? `${SITE_NAME} ✦ ${SITE_TAGLINE}` : `${title} · ${SITE_NAME}`;

  return {
    title: { absolute: fullTitle },
    description,
    keywords: keywords ?? SITE_KEYWORDS,
    alternates: { canonical: url },
    openGraph: {
      title: fullTitle,
      description,
      url,
      siteName: SITE_NAME,
      type: 'website',
      images: [{ url: `${siteUrl()}${image}`, width: 1200, height: 630, alt: `${SITE_NAME} — ${SITE_TAGLINE}` }],
    },
    twitter: {
      card: 'summary_large_image',
      title: fullTitle,
      description,
      images: [`${siteUrl()}${image}`],
    },
  };
}

/** JSON-LD builder — Application schema for the landing page. */
export function softwareApplicationJsonLd(inviteUrl: string | null): string {
  const json = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: SITE_NAME,
    applicationCategory: 'GameApplication',
    operatingSystem: 'Discord',
    description: SITE_DESCRIPTION,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    ...(inviteUrl ? { sameAs: [inviteUrl] } : {}),
  };
  return JSON.stringify(json);
}

/** JSON-LD builder — WebSite with SearchAction (docs search). */
export function websiteJsonLd(): string {
  const json = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE_NAME,
    url: siteUrl(),
    description: SITE_DESCRIPTION,
  };
  return JSON.stringify(json);
}
