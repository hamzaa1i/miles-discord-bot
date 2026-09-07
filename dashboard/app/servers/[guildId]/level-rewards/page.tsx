'use client';

/**
 * Level rewards — the roles handed out automatically at each level.
 * Split out of the leveling page into its own route; xp rate and
 * announcements stay on /leveling.
 *
 * Add/remove actions save IMMEDIATELY (each one is a tiny validated
 * PATCH) — so this page has no save bar, just toasts per action.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { endpoints } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { RolePicker } from '@/components/ChannelPicker';
import { Card, Badge, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { EmptyState } from '@/components/EmptyState';
import { useToast } from '@/components/ui/toast';
import type { LevelReward, Settings } from '@/lib/types';

export default function LevelRewardsPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ms = useModuleSettings(gid, 'leveling');
  const [rewards, setRewards] = useState<LevelReward[] | null>(null);
  const [newLevel, setNewLevel] = useState('');
  const [newRole, setNewRole] = useState<string | null>(null);

  // role-name resolution via the dedicated data endpoint
  useEffect(() => {
    if (!ms.settings) return;
    endpoints
      .levelRewards(gid)
      .then((r) => setRewards(r.rewards))
      .catch(() => setRewards([]));
  }, [gid, ms.saved]);

  if (ms.loading) return <LoadingCard label={ms.verifying ? 'verifying permissions…' : 'loading level rewards…'} />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;
  const rewardsDict = (s.rewards as Record<string, string>) ?? {};

  async function addReward() {
    const level = parseInt(newLevel, 10);
    if (!level || level < 1 || !newRole) {
      toast.push('pick a level and a role first ✧', 'error');
      return;
    }
    const next = { ...rewardsDict, [String(level)]: newRole };
    const ok = await ms.patch({ rewards: next });
    if (ok) {
      toast.push(`level ${level} reward saved ✦`, 'success');
      setNewLevel('');
      setNewRole(null);
    }
  }

  async function removeReward(level: number) {
    const next = { ...rewardsDict };
    delete next[String(level)];
    const ok = await ms.patch({ rewards: next });
    if (ok) toast.push(`level ${level} reward removed`, 'info');
  }

  return (
    <ModuleCard
      icon="star"
      title="level rewards"
      description="roles handed out automatically when a member reaches a level"
    >
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Badge tone="lavender">
          {rewards?.length ?? 0} {rewards?.length === 1 ? 'reward' : 'rewards'}
        </Badge>
        <Link
          href={`/servers/${gid}/leveling`}
          className="text-xs text-veloura-lavender transition hover:text-veloura-pink"
        >
          xp rate &amp; announcements live on the leveling page →
        </Link>
      </div>

      <Card>
        <div className="overflow-x-auto">
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
                        remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : rewards === null ? (
            <p className="text-sm text-veloura-muted">loading…</p>
          ) : (
            <EmptyState
              icon="star"
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
              help="must sit below aurelia's top role so she can grant it"
              value={newRole}
              onChange={(v) => setNewRole(v)}
            />
          </div>
          <button onClick={addReward} className="veloura-button-primary !min-h-[44px]">
            ✦ add reward
          </button>
        </div>
      </Card>

      <p className="mt-4 text-center text-xs text-veloura-muted/60">
        each add/remove saves immediately — no save bar needed
      </p>
    </ModuleCard>
  );
}
