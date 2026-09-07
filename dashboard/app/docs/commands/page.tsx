import { CommandsClient } from '@/components/docs/CommandsClient';
import { pageMetadata } from '@/lib/seo';

/**
 * app/docs/commands/page.tsx — the full command reference.
 *
 * Server wrapper (metadata) around the filterable client view; the
 * dataset is auto-generated from COMMANDS.md.
 */

export const metadata = pageMetadata({
  title: 'commands',
  description:
    'every aurelia command — all 168, with permissions, cooldowns, parameters and examples, filterable by category.',
  path: '/docs/commands',
});

export default function CommandsPage() {
  return <CommandsClient />;
}
