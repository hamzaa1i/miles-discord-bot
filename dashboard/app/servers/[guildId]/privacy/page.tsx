'use client';

/**
 * Privacy & danger zone — what aurelia stores, the audit trail, and the
 * careful destructive actions (cache purge).
 */

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints, ApiRequestError } from '@/lib/api';
import { useGuild } from '@/lib/guild';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';
import { SectionHeading } from '@/components/EmptyState';
import { AuditList } from '@/components/AuditList';
import { useToast } from '@/components/ui/toast';
import { nf } from '@/lib/format';

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
  const { audit, reloadAudit, overview } = useGuild();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  async function purgeCache() {
    setBusy(true);
    try {
      await endpoints.action(gid, 'purge_cache');
      toast.push('cache purged — the bot re-reads settings from the database ✦', 'success');
      setTimeout(reloadAudit, 4000);
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'action failed', 'error');
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <>
      <ModuleCard
        icon="🔒"
        title="privacy & danger zone"
        description="what is stored, who can see it, and the careful destructive things"
      >
        <Card>
          <CardTitle icon="📜">what aurelia remembers</CardTitle>
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

        <Card id="danger" className="mt-4 border-veloura-danger/30">
          <CardTitle icon="⚠">danger zone</CardTitle>
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 p-4">
              <div className="min-w-0">
                <p className="text-sm text-veloura-text">purge settings cache</p>
                <p className="mt-0.5 text-xs leading-relaxed text-veloura-muted/80">
                  the bot caches settings for ~60s. purging forces an immediate
                  re-read — useful after external database edits. no data is deleted.
                </p>
              </div>
              {confirming ? (
                <div className="flex gap-2">
                  <button onClick={purgeCache} disabled={busy} className="veloura-button-danger !min-h-[40px]">
                    {busy ? 'purging…' : 'confirm purge'}
                  </button>
                  <button onClick={() => setConfirming(false)} className="veloura-button-ghost !min-h-[40px]">
                    cancel
                  </button>
                </div>
              ) : (
                <button onClick={() => setConfirming(true)} className="veloura-button-danger !min-h-[40px]">
                  purge cache
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 p-4">
              <div className="min-w-0">
                <p className="text-sm text-veloura-text">reset a module to defaults</p>
                <p className="mt-0.5 text-xs leading-relaxed text-veloura-muted/80">
                  every module page carries its own &ldquo;reset to defaults&rdquo; — this
                  is deliberately per-module, never global.
                </p>
              </div>
              <Badge tone="muted">per-module only</Badge>
            </div>
          </div>
        </Card>
      </ModuleCard>

      <SectionHeading icon="✦" right={<Badge tone="muted">last 50</Badge>}>
        audit trail
      </SectionHeading>
      <Card>
        <p className="mb-3 text-xs text-veloura-muted/70">
          every dashboard mutation in this server is logged — who, what, when.
          {overview ? ` ${nf(audit.length)} recent entries.` : ''}
        </p>
        <AuditList entries={audit} limit={50} />
      </Card>
    </>
  );
}
