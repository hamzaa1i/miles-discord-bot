'use client';

/** Nick requests — settings + pending review queue. */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker } from '@/components/ChannelPicker';
import { Card, CardTitle, Badge, LoadingCard, ErrorCard, TextInput } from '@/components/ui/primitives';
import { EmptyState, SectionHeading } from '@/components/EmptyState';
import { useToast } from '@/components/ui/toast';
import { timeAgo } from '@/lib/format';
import type { NickRequest, Settings } from '@/lib/types';

const DEFAULTS: Settings = {
  channel_id: null,
  auto_approve: false,
  cooldown_hours: 24,
};

export default function NickPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ms = useModuleSettings(gid, 'nick', DEFAULTS);
  const [pending, setPending] = useState<NickRequest[] | null>(null);

  useEffect(() => {
    if (!ms.settings) return;
    endpoints
      .nickPending(gid)
      .then((r) => setPending(r.pending ?? []))
      .catch(() => setPending([]));
  }, [gid, ms.saved]);

  if (ms.loading) return <LoadingCard label="loading nickname config…" />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;

  return (
    <>
      <ModuleCard
        icon="pencil"
        title="nickname requests"
        description="gentle name changes — reviewed by the keepers"
      >
        <Card>
          <CardTitle icon="sparkles">review flow</CardTitle>
          <div className="mt-4">
            <ChannelPicker
              id="nick-channel"
              label="review channel"
              help="where requests surface for approval — unset means auto-approve is the only path"
              value={s.channel_id as string | null}
              onChange={(v) => ms.update({ channel_id: v })}
            />
            <div className="mb-4 flex items-center justify-between gap-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 px-4 py-3">
              <div>
                <p className="text-sm text-veloura-text">auto-approve</p>
                <p className="text-xs text-veloura-muted/70">
                  requests apply instantly, no review needed
                </p>
              </div>
              <input
                type="checkbox"
                className="h-5 w-5 accent-[#FFC0CB]"
                checked={Boolean(s.auto_approve)}
                onChange={(e) => ms.update({ auto_approve: e.target.checked })}
                aria-label="auto approve"
              />
            </div>
            <div className="mb-4">
              <label htmlFor="cooldown" className="veloura-label">
                request cooldown (hours)
              </label>
              <TextInput
                id="cooldown"
                type="number"
                min={0}
                max={720}
                value={String(s.cooldown_hours ?? 24)}
                onChange={(e) => ms.update({ cooldown_hours: Number(e.target.value) || 24 })}
              />
            </div>
          </div>
        </Card>
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('nickname config saved ✦', 'success');
        }}
        onRevert={ms.revert}
      />

      <SectionHeading icon="scroll" right={<Badge tone="muted">{pending?.length ?? 0} pending</Badge>}>
        pending requests
      </SectionHeading>
      <Card>
        {pending === null ? (
          <p className="text-sm text-veloura-muted">loading…</p>
        ) : pending.length === 0 ? (
          <EmptyState icon="pencil" title="no pending requests" hint="members use /nick request to submit one" />
        ) : (
          <ul className="divide-y divide-veloura-border/40">
            {pending.map((r) => (
              <li key={String(r.id)} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 text-sm">
                <span className="font-mono text-xs text-veloura-lavender">
                  {r.user_id.slice(0, 10)}…
                </span>
                <span className="text-veloura-muted">
                  <span className="line-through opacity-60">{r.current_nick || '—'}</span>
                  <span className="mx-2 text-veloura-pink">→</span>
                  <span className="text-veloura-text">{r.requested_nick}</span>
                </span>
                <span className="ml-auto text-xs text-veloura-muted/60">{timeAgo(r.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-veloura-muted/60">
          approve or deny in discord — the review embed carries its own buttons
        </p>
      </Card>
    </>
  );
}
