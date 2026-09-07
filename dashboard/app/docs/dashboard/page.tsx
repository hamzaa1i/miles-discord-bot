import Link from 'next/link';
import { DocsBreadcrumb } from '@/components/docs/DocsBreadcrumb';

import { CodeBlock } from '@/components/docs/CodeBlock';
import { ShareButtons } from '@/components/site/ShareButtons';
import { pageMetadata } from '@/lib/seo';

/**
 * app/docs/dashboard/page.tsx — how to use the web dashboard.
 */

export const metadata = pageMetadata({
  title: 'dashboard guide',
  description:
    'login with discord, pick a server, and configure every aurelia feature visually — live pickers, previews, one-click actions and a full audit log.',
  path: '/docs/dashboard',
});

const SECTIONS = [
  {
    id: 'login',
    title: 'logging in',
    body: 'the dashboard talks to discord via oauth2 with the identify + guilds scopes. you log in with your discord account; only servers where you hold the manage server permission appear in the list. tokens live in an httpOnly cookie — client-side javascript can never read them.',
  },
  {
    id: 'navigation',
    title: 'finding your way around',
    body: 'the sidebar groups 34 module pages into core · ai & engagement · moderation · members · roles · community · utility · server. every item highlights exactly when you are on it, and the browser URL always mirrors where you are — bookmark freely.',
  },
  {
    id: 'pickers',
    title: 'live pickers',
    body: 'channel and role dropdowns are fetched live from discord (5-minute cache), not typed ids — you pick from the same channels you see in the client. options that look greyed out are categories or roles aurelia cannot mention.',
  },
  {
    id: 'actions',
    title: 'one-click actions',
    body: 'buttons like “post qotd now”, “test welcome” or “end giveaway” queue a live action that the running bot executes within seconds — same code path as the slash commands, same permissions, same audit trail.',
  },
  {
    id: 'audit',
    title: 'the audit log',
    body: 'every settings change and live action is recorded with who, when, what and the diff. the audit tab on your server overview is the source of truth when three admins share one bot.',
  },
  {
    id: 'privacy',
    title: 'privacy & danger zone',
    body: 'the privacy page shows per-user data controls; the danger zone holds the destructive resets. everything there is double-confirmed and lands in the audit log too.',
  },
];

export default function DashboardGuide() {
  return (
    <>
      <DocsBreadcrumb page="dashboard guide" />

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">guide</p>
        <h1 className="font-heading mt-2 text-4xl text-veloura-text">the dashboard ✦</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
          34 module pages wrapped in veloura — configure everything visually
          while the slash commands keep working. this page explains what
          you are looking at once you log in.
        </p>
        <p className="mt-4">
          <Link href="/login" className="veloura-button-primary px-6 text-sm">
            open the dashboard
          </Link>
        </p>
      </header>

      <nav aria-label="on this page" className="no-print veloura-card mb-8 p-4">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-veloura-muted/70">
          on this page
        </p>
        <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="text-xs text-veloura-pink hover:underline">
                {s.title}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="space-y-8">
        {SECTIONS.map((s) => (
          <section key={s.id} id={s.id} className="scroll-mt-24">
            <h2 className="font-heading text-2xl text-veloura-text">{s.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-veloura-muted">{s.body}</p>
          </section>
        ))}
      </div>

      <section className="mt-10">
        <h2 className="font-heading text-2xl text-veloura-text">quick reference</h2>
        <p className="mt-2 text-sm text-veloura-muted">
          the three things people ask for in the first five minutes:
        </p>
        <CodeBlock title="where things live">{`/servers                     pick a server (manage server required)
/servers/[guild-id]          overview: stats, features, activity
/servers/[guild-id]/welcome  welcome cards + live preview`}</CodeBlock>
        <p className="mt-3 text-sm leading-relaxed text-veloura-muted">
          the dashboard is part of the managed aurelia deployment — source
          and deployment notes are privately maintained. stuck on login or
          a setting? the support server answers fast, and the{' '}
          <Link href="/docs/api" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
            api guide
          </Link>{' '}
          documents every endpoint the dashboard itself uses.
        </p>
      </section>

      <ShareButtons compact className="mt-10 no-print" text="aurelia's dashboard — configure every discord feature visually ✦" />
    </>
  );
}
