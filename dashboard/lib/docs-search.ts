/**
 * lib/docs-search.ts — client-side search index for the docs site.
 *
 * Built at import time from the generated commands dataset, the module
 * docs and the static pages — then queried with Fuse.js (fuzzy, weighted
 * title > keywords > description). No server, no external service.
 */

import Fuse from 'fuse.js';
import { DOCS_COMMANDS } from '@/lib/docs-commands-data';
import { MODULE_DOCS } from '@/lib/docs-modules';

export interface SearchEntry {
  title: string;
  path: string;
  type: 'page' | 'command' | 'module';
  hint: string;
}

const STATIC_PAGES: SearchEntry[] = [
  { title: 'docs home', path: '/docs', type: 'page', hint: 'start here' },
  { title: 'getting started', path: '/docs/getting-started', type: 'page', hint: 'add the bot, run /setup' },
  { title: 'all commands', path: '/docs/commands', type: 'page', hint: 'the full reference' },
  { title: 'dashboard guide', path: '/docs/dashboard', type: 'page', hint: 'configure visually' },
  { title: 'faq', path: '/docs/faq', type: 'page', hint: 'soft questions, soft answers' },
  { title: 'api docs', path: '/docs/api', type: 'page', hint: 'public endpoints for developers' },
  { title: 'changelog', path: '/changelog', type: 'page', hint: 'every release' },
  { title: 'public stats', path: '/stats', type: 'page', hint: 'live bot vitals' },
];

export const SEARCH_INDEX: SearchEntry[] = [
  ...STATIC_PAGES,
  ...MODULE_DOCS.map((m) => ({
    title: m.title,
    path: `/docs/modules/${m.slug}`,
    type: 'module' as const,
    hint: m.tagline,
  })),
  ...DOCS_COMMANDS.flatMap((cat) =>
    cat.commands.map((cmd) => ({
      title: cmd.name,
      path: `/docs/commands#${cmd.name.replace('/', '').replace(/\s+/g, '-')}`,
      type: 'command' as const,
      hint: cat.category,
    })),
  ),
];

const fuse = new Fuse(SEARCH_INDEX, {
  keys: [
    { name: 'title', weight: 0.6 },
    { name: 'hint', weight: 0.3 },
    { name: 'type', weight: 0.1 },
  ],
  threshold: 0.35,
  ignoreLocation: true,
  minMatchCharLength: 2,
});

export function searchDocs(query: string, limit = 12): SearchEntry[] {
  if (query.trim().length < 2) return [];
  return fuse.search(query.trim(), { limit }).map((r) => r.item);
}
