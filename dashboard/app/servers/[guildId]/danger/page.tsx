'use client';

/**
 * Danger zone — the careful destructive actions + the audit trail.
 * Split out of the privacy page into its own route: privacy explains
 * what is stored, this page does the (reversible-with-care) actions.
 */

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { endpoints, ApiRequestError } from '@/lib/api';
import { useGuild } from '@/lib/guild';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';
import { SectionHeading } from '@/components/EmptyState';
import { AuditList } from '@/components/AuditList';
import { useToast } from '@/components/ui/toast';
import { nf } from '@/lib/format';

export default function DangerPage() {
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
        icon="shieldAlert"
        title="danger zone"
        description="careful destructive actions and the paper trail that follows them"
      >
        <Card className="border-veloura-danger/30">
          <CardTitle icon="shieldAlert">actions</CardTitle>
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

        <p className="mt-4 text-xs leading-relaxed text-veloura-muted/70">
          wondering what data aurelia keeps on this server?{' '}
          <Link
            href={`/servers/${gid}/privacy`}
            className="text-veloura-lavender transition hover:text-veloura-pink"
          >
            the privacy page lists it table by table →
          </Link>
        </p>
      </ModuleCard>

      <SectionHeading icon="sparkles" right={<Badge tone="muted">last 50</Badge>}>
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
