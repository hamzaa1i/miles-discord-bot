import Link from 'next/link';

import { Icon, IconName } from '@/components/icons';
import { DOCS_COMMAND_COUNT } from '@/lib/docs-commands-data';
import { MODULE_DOCS } from '@/lib/docs-modules';
import { botInviteUrl, COMMAND_COUNT } from '@/lib/marketing';
import { pageMetadata, websiteJsonLd } from '@/lib/seo';
import { ShareButtons } from '@/components/site/ShareButtons';

/**
 * app/docs/page.tsx — documentation home. Card grid into each guide +
 * the module directory. The heavy content (commands, modules) is
 * generated from COMMANDS.md / the module registry.
 */

export const metadata = pageMetadata({
  title: 'documentation',
  description:
    'every aurelia command, module and dashboard page explained — getting started, the full command reference, per-module guides and the api.',
  path: '/docs',
});

const GUIDES: {
  href: string;
  icon: IconName | string;
  title: string;
  desc: string;
  tag: string;
}[] = [
  {
    href: '/docs/getting-started',
    icon: 'sparkles',
    title: 'getting started',
    desc: 'add aurelia to your server, run the two-minute setup wizard and learn the three ways to talk to her.',
    tag: 'start here',
  },
  {
    href: '/docs/commands',
    icon: 'wand',
    title: 'all commands',
    desc: `the complete reference — every one of the ${COMMAND_COUNT} commands with permissions, cooldowns and examples.`,
    tag: `${DOCS_COMMAND_COUNT} documented`,
  },
  {
    href: '/docs/modules',
    icon: 'moon',
    title: 'modules',
    desc: `deep dives per feature — welcome, leveling, qotd, moderation, ai and ${MODULE_DOCS.length - 5} more.`,
    tag: `${MODULE_DOCS.length} modules`,
  },
  {
    href: '/docs/dashboard',
    icon: 'settings',
    title: 'dashboard guide',
    desc: 'login, pick a server, configure everything visually — live pickers, previews and one-click actions.',
    tag: '34 pages',
  },
  {
    href: '/docs/faq',
    icon: 'helpCircle',
    title: 'faq',
    desc: 'the soft questions and their soft answers — pricing, data, self-hosting, support.',
    tag: 'quick answers',
  },
  {
    href: '/docs/api',
    icon: 'zap',
    title: 'api',
    desc: 'public stats + changelog endpoints for developers, and the auth model behind the dashboard api.',
    tag: 'for builders',
  },
];

export default function DocsHome() {
  const invite = botInviteUrl();
  return (
    <>
      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">documentation</p>
        <h1 className="font-heading mt-2 text-4xl text-veloura-text">the aurelia manual ✦</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
          everything she can do, written down softly. search from the sidebar
          (⌘k), follow the cross-references, or start at the beginning.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {invite && (
            <a
              href={invite}
              target="_blank"
              rel="noopener noreferrer"
              className="veloura-button-primary px-5 text-sm"
            >
              <Icon name="plus" size={15} />
              add to discord
            </a>
          )}
          <ShareButtons compact className="no-print" />
        </div>
      </header>

      <section aria-label="guides" className="grid gap-4 sm:grid-cols-2">
        {GUIDES.map((g) => (
          <Link
            key={g.href}
            href={g.href}
            className="group veloura-card relative p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-veloura-pink/40 hover:shadow-glow"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-veloura-pink/10 text-veloura-pink transition-transform duration-300 group-hover:scale-110">
                <Icon name={g.icon} size={18} />
              </span>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-heading text-lg text-veloura-text">{g.title}</h2>
                  <span className="rounded-full bg-veloura-card-hover px-2 py-0.5 text-[10px] uppercase tracking-wider text-veloura-muted">
                    {g.tag}
                  </span>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-veloura-muted">{g.desc}</p>
              </div>
              <span
                className="ml-auto shrink-0 text-veloura-pink opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100"
                aria-hidden
              >
                →
              </span>
            </div>
          </Link>
        ))}
      </section>

      <section aria-label="module directory" className="mt-12">
        <h2 className="font-heading text-2xl text-veloura-text">module directory</h2>
        <p className="mt-1.5 text-sm text-veloura-muted">
          every dashboard page has a guide — here are the most-read:
        </p>
        <ul className="mt-4 flex flex-wrap gap-2">
          {['welcome', 'leveling', 'qotd', 'automod', 'ai', 'giveaways', 'starboard', 'privacy'].map(
            (slug) => {
              const m = MODULE_DOCS.find((x) => x.slug === slug);
              if (!m) return null;
              return (
                <li key={slug}>
                  <Link
                    href={`/docs/modules/${slug}`}
                    className="veloura-button-ghost px-3.5 py-1.5 text-xs"
                  >
                    {m.title}
                  </Link>
                </li>
              );
            },
          )}
        </ul>
        <p className="mt-4 text-sm text-veloura-muted">
          all {MODULE_DOCS.length} modules live in the sidebar —{' '}
          <Link href="/docs/modules/welcome" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            start with welcome
          </Link>
          .
        </p>
      </section>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: websiteJsonLd() }}
      />
    </>
  );
}
