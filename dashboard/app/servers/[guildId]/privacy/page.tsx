'use client';

/**
 * Privacy — what aurelia stores, where, and who controls it.
 * The destructive actions + audit trail live on their own /danger page.
 */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle } from '@/components/ui/primitives';

const DATA_TABLE = [
  { what: 'guild settings', where: 'supabase (welcome, leveling, qotd, …)', who: 'server staff' },
  { what: 'warnings & mod log', where: 'supabase · warnings', who: 'server staff' },
  { what: 'levels & xp', where: 'supabase · user_levels', who: 'members' },
  { what: 'ai conversation memory', where: 'supabase · conversation_memory (7-day purge)', who: 'members — /forget, /privacy' },
  { what: 'birthdays & profiles', where: 'supabase · user_profiles', who: 'members' },
  { what: 'command usage', where: 'supabase · command_usage (analytics)', who: 'server staff' },
];

export default function PrivacyPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);

  return (
    <ModuleCard
      icon="lock"
      title="privacy"
      description="what is stored, where it lives, and who can see it"
    >
      <Card>
        <CardTitle icon="scroll">what aurelia remembers</CardTitle>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-veloura-border/60 text-left text-xs uppercase tracking-wider text-veloura-muted">
                <th className="pb-2 pr-4">data</th>
                <th className="pb-2 pr-4">where</th>
                <th className="pb-2">control</th>
              </tr>
            </thead>
            <tbody>
              {DATA_TABLE.map((row) => (
                <tr key={row.what} className="border-b border-veloura-border/30">
                  <td className="py-3 pr-4 text-veloura-text">{row.what}</td>
                  <td className="py-3 pr-4 text-xs text-veloura-muted">{row.where}</td>
                  <td className="py-3 text-xs text-veloura-lavender">{row.who}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs leading-relaxed text-veloura-muted/70">
          members can export or erase everything personal with{' '}
          <code className="text-veloura-lavender">/privacy export</code> and{' '}
          <code className="text-veloura-lavender">/privacy delete</code> — fourteen tables,
          one command.
        </p>
      </Card>

      <p className="mt-5 text-xs leading-relaxed text-veloura-muted/70">
        cache purges, resets and the audit trail of every dashboard change
        live on{' '}
        <Link
          href={`/servers/${gid}/danger`}
          className="text-veloura-lavender transition hover:text-veloura-pink"
        >
          the danger zone page →
        </Link>
      </p>
    </ModuleCard>
  );
}
