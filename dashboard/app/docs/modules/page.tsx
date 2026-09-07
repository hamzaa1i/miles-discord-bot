import Link from 'next/link';
import { DocsBreadcrumb } from '@/components/docs/DocsBreadcrumb';

import { MODULE_DOCS } from '@/lib/docs-modules';
import { pageMetadata } from '@/lib/seo';
import { ShareButtons } from '@/components/site/ShareButtons';

/**
 * app/docs/modules/page.tsx — index of every module deep dive.
 * The [module] dynamic route renders each entry; this page is the
 * directory (and the sitemap source for module paths).
 */

export const metadata = pageMetadata({
  title: 'modules',
  description:
    'deep dives for every aurelia module — welcome cards, leveling, qotd, ai chat, moderation, giveaways and more.',
  path: '/docs/modules',
});

export default function ModulesIndex() {
  return (
    <>
      <DocsBreadcrumb page="modules" />

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">modules</p>
        <h1 className="font-heading mt-2 text-4xl text-veloura-text">
          every module, explained ✦
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
          each dashboard page has a companion guide: what the module does,
          which commands drive it, and the small tips that make it sing.
        </p>
        <ShareButtons compact className="mt-4 no-print" />
      </header>

      <ul className="grid gap-3 sm:grid-cols-2">
        {MODULE_DOCS.map((m) => (
          <li key={m.slug}>
            <Link
              href={`/docs/modules/${m.slug}`}
              className="group veloura-card block p-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-veloura-pink/40 hover:shadow-glow"
            >
              <h2 className="font-heading text-base text-veloura-text group-hover:text-veloura-lavender">
                {m.title}
              </h2>
              <p className="mt-1 text-xs text-veloura-lavender/80">“{m.tagline}”</p>
              <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-veloura-muted">
                {m.description}
              </p>
              <p className="mt-2.5 font-mono text-[10px] text-veloura-muted/60">
                {m.commands.slice(0, 3).join(' · ')}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
