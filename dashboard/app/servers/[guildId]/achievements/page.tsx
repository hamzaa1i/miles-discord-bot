'use client';

/** Achievements — leaderboard of unlocked badges. */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, Badge, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { EmptyState } from '@/components/EmptyState';
import { timeAgo } from '@/lib/format';
import type { LeaderboardRow } from '@/lib/types';

export default function AchievementsPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    endpoints
      .achievements(gid)
      .then((r) => setRows(r.leaderboard ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : 'could not load'));
  }, [gid]);

  return (
    <ModuleCard
      icon="🏅"
      title="achievements"
      description="fifteen quiet badges, earned by simply being there"
    >
      {error ? (
        <ErrorCard message={error} />
      ) : rows === null ? (
        <LoadingCard label="counting the badges…" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon="🏅"
          title="no badges earned yet"
          hint="badges unlock as members chat, react, streak and stay — /achievements list shows the catalog"
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
