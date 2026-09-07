'use client';

/** Achievements — the full 15-badge catalog (locked included) + leaderboard. */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, Badge, LoadingCard, ErrorCard, Skeleton } from '@/components/ui/primitives';
import { EmptyState, SectionHeading } from '@/components/EmptyState';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';
import { timeAgo } from '@/lib/format';
import type { AchievementBadge, LeaderboardRow } from '@/lib/types';

const RARITY_TONE: Record<string, string> = {
  common: 'text-veloura-muted border-veloura-border/60',
  uncommon: 'text-veloura-success border-veloura-success/40',
  rare: 'text-[#7EB6FF] border-[#7EB6FF]/40',
  epic: 'text-[#C49BFF] border-[#C49BFF]/40',
  legendary: 'text-[#FFD700] border-[#FFD700]/50',
};

export default function AchievementsPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null);
  const [catalog, setCatalog] = useState<AchievementBadge[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    endpoints
      .achievements(gid)
      .then((r) => {
        setRows(r.leaderboard ?? []);
        setCatalog(r.catalog ?? []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'could not load'));
  }, [gid]);

  const unlockedCount = (catalog ?? []).filter((b) => b.unlocked_by > 0).length;

  return (
    <ModuleCard
      icon="trophy"
      title="achievements"
      description="fifteen quiet badges, earned by simply being there — the whole catalog, locked ones included"
    >
      {error ? (
        <ErrorCard message={error} />
      ) : catalog === null ? (
        <div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </Card>
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* badge catalog — every achievement, locked or earned */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {catalog.map((b) => {
              const earned = b.unlocked_by > 0;
              return (
                <Card
                  key={b.key}
                  className={cn(
                    'flex items-center gap-3 transition',
                    earned ? 'border-veloura-pink/30' : 'opacity-75',
                  )}
                >
                  <div
                    aria-hidden
                    className={cn(
                      'flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-lg',
                      RARITY_TONE[b.rarity] ?? RARITY_TONE.common,
                    )}
                  >
                    {b.emoji}
                  </div>
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-sm text-veloura-text">
                      {b.name}
                      {!earned && <Icon name="lock" size={12} className="text-veloura-muted/60" />}
                    </p>
                    <p className="truncate text-xs text-veloura-muted/80">{b.description}</p>
                    <p className="mt-0.5 text-[11px] text-veloura-muted/60">
                      {b.rarity}
                      {earned ? ` · unlocked by ${b.unlocked_by} member${b.unlocked_by === 1 ? '' : 's'}` : ' · not yet earned'}
                    </p>
                  </div>
                </Card>
              );
            })}
          </div>
          <p className="mt-3 text-xs text-veloura-muted/60">
            {unlockedCount} of {catalog.length || 15} badges have been earned in this server —
            members can check their own with <code className="text-veloura-lavender">/achievements</code>
          </p>
        </>
      )}

      {/* leaderboard */}
      <SectionHeading icon="trophy">leaderboard</SectionHeading>
      {rows === null ? (
        <LoadingCard label="counting the badges…" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon="sparkles"
          title="no badges earned yet"
          hint="badges unlock as members chat, react, streak and stay — the catalog above shows every one"
        />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead>
                <tr className="border-b border-veloura-border/60 text-left text-xs uppercase tracking-wider text-veloura-muted">
                  <th className="pb-2 pr-4">#</th>
                  <th className="pb-2 pr-4">member</th>
                  <th className="pb-2 pr-4 text-right">badges</th>
                  <th className="pb-2 text-right">latest</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.user_id} className="border-b border-veloura-border/30">
                    <td className="py-3 pr-4">
                      <Badge tone={i === 0 ? 'pink' : 'muted'}>{i + 1}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-veloura-text">{r.display_name}</td>
                    <td className="py-3 pr-4 text-right text-veloura-lavender">
                      {r.achievements} / 15
                    </td>
                    <td className="py-3 text-right text-xs text-veloura-muted/70">
                      {timeAgo(r.latest)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </ModuleCard>
  );
}
