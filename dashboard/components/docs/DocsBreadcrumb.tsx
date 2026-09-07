import Link from 'next/link';

/**
 * components/docs/DocsBreadcrumb.tsx — PHASE N (19.3).
 *
 * Shared breadcrumb for every docs page. "docs" is ALWAYS clickable
 * (back to /docs) so nobody has to rely on the browser Back button:
 *
 *     docs / faq
 *     docs / modules / welcome
 *
 * The last crumb is the current page (plain text, aria-current="page").
 * Print styles hide nothing — the breadcrumb stays in print output as a
 * page locator.
 */

export function DocsBreadcrumb({
  items,
  page,
}: {
  /** Intermediate crumbs (label + href); the final crumb is passed as
   * `page` and rendered as plain text. */
  items?: { label: string; href: string }[];
  /** The current page — rendered as plain text, not a link. */
  page: string;
}) {
  const trail = items ?? [];
  return (
    <nav
      aria-label="breadcrumb"
      className="mb-4 text-xs text-veloura-muted/70"
    >
      <Link href="/docs" className="hover:text-veloura-pink">
        docs
      </Link>
      {trail.map((c) => (
        <span key={c.href}>
          <span aria-hidden> / </span>
          <Link href={c.href} className="hover:text-veloura-pink">
            {c.label}
          </Link>
        </span>
      ))}
      <span aria-hidden> / </span>
      <span className="text-veloura-text" aria-current="page">
        {page}
      </span>
    </nav>
  );
}
