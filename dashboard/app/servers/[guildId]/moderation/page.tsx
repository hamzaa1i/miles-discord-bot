'use client';

/** Moderation — settings: log channel, admin role, thresholds, antilink.
 * The warnings case history lives on its own /warnings page now. */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker, RolePicker, ChannelMultiPicker } from '@/components/ChannelPicker';
import { Card, CardTitle, Select, TextInput, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import type { Settings } from '@/lib/types';

const DEFAULTS: Settings = {
  log_channel_id: null,
  admin_role_id: null,
  max_warns_before_ban: 3,
  warn_threshold_count: 3,
  warn_threshold_action: 'timeout',
  antispam_enabled: false,
  antilink_channels: null,
};

const THRESHOLD_ACTIONS = [
  { value: 'timeout', label: 'timeout' },
  { value: 'kick', label: 'kick' },
  { value: 'ban', label: 'ban' },
];

export default function ModerationPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ms = useModuleSettings(gid, 'moderation', DEFAULTS);

  if (ms.loading)
    return <LoadingCard label={ms.verifying ? 'verifying permissions…' : 'loading moderation config…'} />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;

  return (
    <>
      <ModuleCard
        icon="swords"
        title="moderation"
        description="warnings, thresholds and the quiet guardrails"
        enabled={Boolean(s.antispam_enabled)}
        toggledLabel="antispam on"
        onToggle={async (next) => {
          ms.update({ antispam_enabled: next });
          const ok = await ms.patch({ antispam_enabled: next });
          if (ok) toast.push(`antispam ${next ? 'enabled' : 'disabled'} ✦`, 'success');
        }}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle icon="users">roles &amp; logs</CardTitle>
            <div className="mt-4">
              <ChannelPicker
                id="mod-log"
                label="moderation log channel"
                value={s.log_channel_id as string | null}
                onChange={(v) => ms.update({ log_channel_id: v })}
              />
              <RolePicker
                id="admin-role"
                label="admin role"
                help="members who can use moderation commands"
                value={s.admin_role_id as string | null}
                onChange={(v) => ms.update({ admin_role_id: v })}
              />
            </div>
          </Card>

          <Card>
            <CardTitle icon="swords">warning threshold</CardTitle>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div className="mb-4">
                <label htmlFor="threshold-count" className="veloura-label">
                  warn count
                </label>
                <TextInput
                  id="threshold-count"
                  type="number"
                  min={1}
                  max={10}
                  value={String(s.warn_threshold_count ?? 3)}
                  onChange={(e) => ms.update({ warn_threshold_count: Number(e.target.value) || 3 })}
                />
              </div>
              <div className="mb-4">
                <label htmlFor="threshold-action" className="veloura-label">
                  action
                </label>
                <Select
                  id="threshold-action"
                  value={String(s.warn_threshold_action ?? 'timeout')}
                  onChange={(e) => ms.update({ warn_threshold_action: e.target.value })}
                >
                  {THRESHOLD_ACTIONS.map((a) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="mb-4">
              <label htmlFor="max-warns" className="veloura-label">
                max warns before ban
              </label>
              <TextInput
                id="max-warns"
                type="number"
                min={1}
                max={20}
                value={String(s.max_warns_before_ban ?? 3)}
                onChange={(e) => ms.update({ max_warns_before_ban: Number(e.target.value) || 3 })}
              />
            </div>
            <ChannelMultiPicker
              label="antilink channels"
              help="links are removed in these channels"
              value={Array.isArray(s.antilink_channels) ? (s.antilink_channels as string[]) : []}
              onChange={(v) => ms.update({ antilink_channels: v.length ? v : null })}
            />
          </Card>
        </div>

        <p className="mt-5 text-xs leading-relaxed text-veloura-muted/70">
          the full warning history — searchable, paginated, live — lives on{' '}
          <Link
            href={`/servers/${gid}/warnings`}
            className="text-veloura-lavender transition hover:text-veloura-pink"
          >
            the warnings page →
          </Link>
        </p>
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('moderation config saved ✦', 'success');
        }}
        onRevert={ms.revert}
      />
    </>
  );
}
