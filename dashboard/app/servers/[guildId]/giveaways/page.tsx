'use client';

/** Giveaways — active cards (end early) + past list (delete). */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { EmptyState, SectionHeading } from '@/components/EmptyState';
import { useToast } from '@/components/ui/toast';
import { Icon } from '@/components/icons';
import { timeAgo, nf } from '@/lib/format';
import type { Giveaway } from '@/lib/types';

function endsIn(epoch: number): string {
  const diff = epoch * 1000 - Date.now();
  if (diff <= 0) return 'ended';
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m left`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours}h ${mins % 60}m left`;
  return `${Math.floor(hours / 24)}d left`;
}

export default function GiveawaysPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const [data, setData] = useState<{ active: Giveaway[]; past: Giveaway[] } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  function reload() {
    endpoints
      .giveaways(gid)
      .then(setData)
      .catch(() => setData({ active: [], past: [] }));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gid]);

  async function endGiveway(gw: Giveaway) {
    setBusy(gw.id);
    try {
      await endpoints.action(gid, 'giveaway_end', { giveaway_id: gw.id });
      toast.push('ending queued — winners drawn within ~5s ✦', 'success');
      setTimeout(reload, 6000);
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'failed to queue end', 'error');
    } finally {
      setBusy(null);
    }
  }

  async function deleteGiveaway(gw: Giveaway) {
    try {
      await endpoints.deleteData(gid, 'giveaways', gw.id);
      setData((d) =>
        d ? { active: d.active, past: d.past.filter((x) => x.id !== gw.id) } : d,
      );
      toast.push('giveaway deleted', 'info');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'delete failed', 'error');
    }
  }

  return (
    <ModuleCard
      icon="gift"
      title="giveaways"
      description="gifts from the void — start them in discord with /giveaway start"
    >
      <SectionHeading icon="sparkles" right={<Badge tone="pink">{data?.active.length ?? 0} active</Badge>}>
        running now
      </SectionHeading>

      {data === null ? (
        <LoadingCard label="loading giveaways…" />
      ) : data.active.length === 0 ? (
        <EmptyState icon="gift" title="no active giveaways" hint="start one with /giveaway start prize:... duration:..." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {data.active.map((gw) => (
            <Card key={gw.id} className="flex flex-col gap-3 border-veloura-pink/30">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate font-heading text-lg text-veloura-text">{gw.prize}</h3>
                  <p className="mt-1 text-xs text-veloura-muted">
                    hosted by {gw.host_name ?? 'a keeper'} · id {gw.id}
                  </p>
                </div>
                <Badge tone="pink">{endsIn(gw.ends_at)}</Badge>
              </div>
              <div className="flex flex-wrap gap-2 text-xs text-veloura-muted/80">
                <Badge tone="muted">{nf(gw.entries?.length ?? 0)} entrants</Badge>
                <Badge tone="muted">{gw.winners_count ?? 1} winner(s)</Badge>
              </div>
              <button
                onClick={() => endGiveway(gw)}
                disabled={busy === gw.id}
                className="veloura-button-ghost mt-auto !min-h-[40px] text-xs"
              >
                {busy === gw.id ? 'ending…' : '✧ end early'}
              </button>
            </Card>
          ))}
        </div>
      )}

      <SectionHeading icon="📜" right={<Badge tone="muted">{data?.past.length ?? 0} past</Badge>}>
        ended
      </SectionHeading>
      {data && data.past.length > 0 ? (
        <Card>
          <ul className="divide-y divide-veloura-border/40">
            {data.past.map((gw) => (
              <li key={gw.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-3 text-sm">
                <span className="min-w-0 flex-1 truncate text-veloura-text">{gw.prize}</span>
                <Badge tone="muted">{gw.entries?.length ?? 0} entrants</Badge>
                <span className="text-xs text-veloura-muted/60">{timeAgo(gw.created_at)}</span>
                <button
                  onClick={() => deleteGiveaway(gw)}
                  className="flex h-11 w-11 items-center justify-center rounded-[10px] border border-veloura-danger/30 text-veloura-danger transition hover:bg-veloura-danger/10"
                  aria-label={`delete giveaway ${gw.id}`}
                >
                  <Icon name="trash" size={15} />
                </button>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <EmptyState icon="sparkles" title="no past giveaways" hint="ended giveaways stay listed here for 30 days" />
      )}
    </ModuleCard>
  );
}
