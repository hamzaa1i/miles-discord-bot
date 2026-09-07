'use client';

/** Leveling — xp rate, announce mode, level-up message.
 * The role-rewards table lives on its own /level-rewards page now. */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker } from '@/components/ChannelPicker';
import { MessageEditor } from '@/components/MessageEditor';
import { Card, CardTitle, Badge, Select, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import type { Settings } from '@/lib/types';

const DEFAULTS: Settings = {
  enabled: true,
  channel_id: null,
  rate: 1.0,
  level_up_message: null,
  level_up_channel_mode: 'active',
};

const CHANNEL_MODES = [
  { value: 'active', label: 'active channel — announce where they leveled' },
  { value: 'configured', label: 'configured channel — always the same place' },
  { value: 'dm', label: 'dm — a quiet congratulations' },
  { value: 'none', label: 'none — silent leveling' },
];

export default function LevelingPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ms = useModuleSettings(gid, 'leveling', DEFAULTS);

  if (ms.loading)
    return <LoadingCard label={ms.verifying ? 'verifying permissions…' : 'loading leveling config…'} />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;
  const rate = Number(s.rate ?? 1);

  return (
    <>
      <ModuleCard
        icon="star"
        title="leveling"
        description="xp, levels and role rewards — the quiet economy of presence"
        enabled={Boolean(s.enabled)}
        onToggle={async (next) => {
          ms.update({ enabled: next });
          const ok = await ms.patch({ enabled: next });
          if (ok) toast.push(`leveling ${next ? 'enabled' : 'disabled'} ✦`, 'success');
        }}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle icon="sparkles">xp flow</CardTitle>
            <div className="mt-4">
              <div className="mb-6">
                <label htmlFor="rate" className="veloura-label">
                  xp per message
                </label>
                <div className="flex items-center gap-4">
                  <input
                    id="rate"
                    type="range"
                    min={0.5}
                    max={10}
                    step={0.5}
                    value={rate}
                    onChange={(e) => ms.update({ rate: Number(e.target.value) })}
                    className="flex-1"
                  />
                  <Badge tone="pink">{rate.toFixed(1)} xp</Badge>
                </div>
                <p className="mt-2 text-xs text-veloura-muted/80">
                  the bot adds a small cooldown between messages so chatting isn&apos;t a grind
                </p>
              </div>

              <div className="mb-4">
                <label htmlFor="mode" className="veloura-label">
                  level-up announcement
                </label>
                <Select
                  id="mode"
                  value={String(s.level_up_channel_mode ?? 'active')}
                  onChange={(e) => ms.update({ level_up_channel_mode: e.target.value })}
                >
                  {CHANNEL_MODES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              </div>

              {s.level_up_channel_mode === 'configured' && (
                <ChannelPicker
                  id="announce-channel"
                  label="announce channel"
                  value={s.channel_id as string | null}
                  onChange={(v) => ms.update({ channel_id: v })}
                />
              )}
            </div>
          </Card>

          <Card>
            <CardTitle icon="✧">level-up message</CardTitle>
            <div className="mt-4">
              <MessageEditor
                label="announcement text"
                help="empty uses the built-in message · {user}, {server}, {level} available"
                placeholder=""
                value={String(s.level_up_message ?? '')}
                onChange={(v) => ms.update({ level_up_message: v || null })}
                rows={5}
              />
            </div>
          </Card>
        </div>

        <p className="mt-5 text-xs leading-relaxed text-veloura-muted/70">
          roles granted automatically at each level are managed on{' '}
          <Link
            href={`/servers/${gid}/level-rewards`}
            className="text-veloura-lavender transition hover:text-veloura-pink"
          >
            the level rewards page →
          </Link>
        </p>
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('leveling config saved ✦', 'success');
        }}
        onRevert={ms.revert}
      />
    </>
  );
}
