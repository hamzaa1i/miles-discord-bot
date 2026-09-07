'use client';

/** Leveling — xp rate, announce mode, level-up message, role rewards table. */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker, RolePicker } from '@/components/ChannelPicker';
import { MessageEditor } from '@/components/MessageEditor';
import { Card, CardTitle, Badge, Select, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import { EmptyState } from '@/components/EmptyState';
import type { LevelReward, Settings } from '@/lib/types';

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
  const [rewards, setRewards] = useState<LevelReward[] | null>(null);
  const [newLevel, setNewLevel] = useState('');
  const [newRole, setNewRole] = useState<string | null>(null);

  // current rewards live inside leveling_settings.rewards — read via the
  // dedicated data endpoint for role-name resolution
  useEffect(() => {
    if (!ms.settings) return;
    endpoints
      .levelRewards(gid)
      .then((r) => setRewards(r.rewards))
      .catch(() => setRewards([]));
  }, [gid, ms.saved]);

  if (ms.loading) return <LoadingCard label="loading leveling config…" />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;
  const rate = Number(s.rate ?? 1);

  function setRewardsDict(next: Record<string, string>) {
    ms.update({ rewards: next });
  }

  const rewardsDict = (s.rewards as Record<string, string>) ?? {};

  async function addReward() {
    const level = parseInt(newLevel, 10);
    if (!level || level < 1 || !newRole) {
      toast.push('pick a level and a role first ✧', 'error');
      return;
    }
    const next = { ...rewardsDict, [String(level)]: newRole };
    setRewardsDict(next);
    setNewLevel('');
    setNewRole(null);
    const ok = await ms.patch({ rewards: next });
    if (ok) toast.push(`level ${level} reward saved ✦`, 'success');
  }

  async function removeReward(level: number) {
    const next = { ...rewardsDict };
    delete next[String(level)];
    setRewardsDict(next);
    const ok = await ms.patch({ rewards: next });
    if (ok) toast.push(`level ${level} reward removed`, 'info');
  }

  return (
    <>
      <ModuleCard
        icon="✩"
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
            <CardTitle icon="✦">xp flow</CardTitle>
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

        {/* rewards table */}
        <Card className="mt-6" id="rewards">
          <CardTitle icon="✦">role rewards</CardTitle>
          <p className="mt-1.5 text-xs text-veloura-muted">
            roles handed out automatically when a member reaches a level
          </p>

          <div className="mt-4 overflow-x-auto">
            {rewards && rewards.length > 0 ? (
              <table className="w-full min-w-[420px] text-sm">
                <thead>
                  <tr className="border-b border-veloura-border/60 text-left text-xs uppercase tracking-wider text-veloura-muted">
                    <th className="pb-2 pr-4">level</th>
                    <th className="pb-2 pr-4">role</th>
                    <th className="pb-2 text-right">remove</th>
                  </tr>
                </thead>
                <tbody>
                  {rewards.map((r) => (
                    <tr key={r.level} className="border-b border-veloura-border/30">
                      <td className="py-3 pr-4">
                        <Badge tone="lavender">lvl {r.level}</Badge>
                      </td>
                      <td className="py-3 pr-4">
                        <span className="flex items-center gap-2">
                          {r.role_color && (
                            <span
                              aria-hidden
                              className="inline-block h-2.5 w-2.5 rounded-full"
                              style={{ background: r.role_color }}
                            />
                          )}
                          {r.role_name ?? `role ${r.role_id}`}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        <button
                          onClick={() => removeReward(r.level)}
                          className="rounded-[10px] border border-veloura-danger/30 px-2.5 py-1 text-xs text-veloura-danger transition hover:bg-veloura-danger/10"
                          aria-label={`remove level ${r.level} reward`}
                        >
                          ✕ remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState
                icon="✩"
                title="no role rewards configured"
                hint="add one below — members earn the role at that level automatically"
              />
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-3">
            <div className="w-28">
              <label htmlFor="new-level" className="veloura-label">
                level
              </label>
              <input
                id="new-level"
                type="number"
                min={1}
                placeholder="10"
                value={newLevel}
                onChange={(e) => setNewLevel(e.target.value)}
                className="veloura-input"
              />
            </div>
            <div className="min-w-[200px] flex-1">
              <RolePicker
                label="role"
                value={newRole}
                onChange={(v) => setNewRole(v)}
              />
            </div>
            <button onClick={addReward} className="veloura-button-primary !min-h-[44px]">
              ✦ add reward
            </button>
          </div>
        </Card>
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
