'use client';

/** AI automod — the watchful gaze. */

import { useParams } from 'next/navigation';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker, ChannelMultiPicker } from '@/components/ChannelPicker';
import { Card, CardTitle, Select, LoadingCard, ErrorCard, TextInput } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import type { Settings } from '@/lib/types';

const DEFAULTS: Settings = {
  enabled: false,
  alert_channel_id: null,
  timeout_minutes: 10,
  min_severity: 'medium',
};

const SEVERITIES = [
  { value: 'low', label: 'low — catch everything, gentle' },
  { value: 'medium', label: 'medium — the balanced gaze' },
  { value: 'high', label: 'high — only clear violations' },
];

// ai_automod watches configured channels — reuse the settings table's
// shape; watched channels come from the same table when present.
const WATCH_KEY = 'watched_channels';

export default function AutomodPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ms = useModuleSettings(gid, 'ai_automod', DEFAULTS);

  if (ms.loading) return <LoadingCard label="waking the gaze…" />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;

  return (
    <>
      <ModuleCard
        icon="shield"
        title="ai automod"
        description="messages pass before a quiet model — severity decides the consequence"
        enabled={Boolean(s.enabled)}
        onToggle={async (next) => {
          ms.update({ enabled: next });
          const ok = await ms.patch({ enabled: next });
          if (ok) toast.push(`ai automod ${next ? 'enabled' : 'disabled'} ✦`, 'success');
        }}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle icon="swords">response</CardTitle>
            <div className="mt-4">
              <div className="mb-4">
                <label htmlFor="timeout-min" className="veloura-label">
                  timeout duration (minutes)
                </label>
                <TextInput
                  id="timeout-min"
                  type="number"
                  min={1}
                  max={1440}
                  value={String(s.timeout_minutes ?? 10)}
                  onChange={(e) => ms.update({ timeout_minutes: Number(e.target.value) || 10 })}
                />
              </div>
              <div className="mb-4">
                <label htmlFor="min-severity" className="veloura-label">
                  minimum severity
                </label>
                <Select
                  id="min-severity"
                  value={String(s.min_severity ?? 'medium')}
                  onChange={(e) => ms.update({ min_severity: e.target.value })}
                >
                  {SEVERITIES.map((sv) => (
                    <option key={sv.value} value={sv.value}>
                      {sv.label}
                    </option>
                  ))}
                </Select>
              </div>
              <ChannelPicker
                id="alert-channel"
                label="alert channel"
                help="where the gaze reports what it caught"
                value={s.alert_channel_id as string | null}
                onChange={(v) => ms.update({ alert_channel_id: v })}
              />
            </div>
          </Card>

          <Card>
            <CardTitle icon="users">scope</CardTitle>
            <div className="mt-4">
              {Array.isArray(s[WATCH_KEY]) ? (
                <ChannelMultiPicker
                  label="watched channels"
                  help="empty means every channel is watched"
                  value={s[WATCH_KEY] as string[]}
                  onChange={(v) => ms.update({ [WATCH_KEY]: v })}
                />
              ) : (
                <div className="rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 p-4 text-sm leading-relaxed text-veloura-muted">
                  <p>
                    <span aria-hidden>👁 </span>
                    when enabled, the gaze watches every channel by default.
                    add <code className="text-veloura-lavender">watched_channels</code> to
                    the settings row to narrow its sight.
                  </p>
                </div>
              )}
            </div>
            <div className="mt-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 p-4 text-xs leading-relaxed text-veloura-muted/80">
              <p className="mb-2 font-semibold text-veloura-lavender">how it works</p>
              <p>
                every message in scope is scored by a small model. at or above the
                minimum severity the member earns a strike — repeated strikes
                escalate to the timeout above. alerts land in the alert channel,
                and everything is logged for review.
              </p>
            </div>
          </Card>
        </div>
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('ai automod saved ✦', 'success');
        }}
        onRevert={ms.revert}
        onResetDefaults={async () => {
          const ok = await ms.resetDefaults();
          if (ok) toast.push('reset to defaults', 'info');
        }}
      />
    </>
  );
}
