/**
 * components/site/SiteFooter.tsx — public site footer.
 *
 * "built by volc · wrapped in veloura ✧" + every link the spec asked
 * for: dashboard, documentation, support server, creator profile.
 *
 * PHASE N (20.3): the repository link became a creator-PROFILE link —
 * the source is privately maintained, and a repo link would 404 for
 * strangers. Attribution is preserved.
 */

import Link from 'next/link';
import { Icon } from '@/components/icons';
import { CREATOR_GITHUB_URL, SUPPORT_SERVER_URL } from '@/lib/marketing';

export function SiteFooter() {
  return (
    <footer className="border-t border-veloura-border/60 bg-veloura-navy-deep/40">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-6 py-10 sm:flex-row sm:justify-between">
        <div className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/aurelia-logo.png"
            alt="aurelia logo — a soft pink four-pointed star"
            width={22}
            height={22}
          />
          <p className="text-sm text-veloura-muted">
            built by volc · wrapped in veloura{' '}
            <span className="twinkle text-veloura-pink" aria-hidden>
              ✧
            </span>
          </p>
        </div>

        <nav aria-label="footer links" className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
          <Link href="/login" className="text-sm text-veloura-muted transition-colors hover:text-veloura-pink">
            dashboard
          </Link>
          <Link href="/docs" className="text-sm text-veloura-muted transition-colors hover:text-veloura-pink">
            documentation
          </Link>
          {SUPPORT_SERVER_URL && (
            <a
              href={SUPPORT_SERVER_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-veloura-muted transition-colors hover:text-veloura-pink"
            >
              support server
            </a>
          )}
          <a
            href={CREATOR_GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-veloura-muted transition-colors hover:text-veloura-pink"
            aria-label="volc on github — aurelia's creator (opens in a new tab)"
          >
            <Icon name="star" size={13} />
            volc
          </a>
        </nav>
      </div>
    </footer>
  );
}
