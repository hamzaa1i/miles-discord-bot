'use client';

/** Statistics — commands/day line, top commands bar, leveling leaderboard. */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints } from '@/lib/api';
import { useGuild } from '@/lib/guild';
import { LineChart, BarChart } from '@/components/StatsChart';
import { Card, CardTitle, Badge, LoadingCard, ErrorCard, Skeleton } from '@/components/ui/primitives';
import { SectionHeading, StatCard, EmptyState } from '@/components/EmptyState';
import { useRealtime } from '@/lib/useRealtime';
import { nf } from '@/lib/format';
import type { StatsData } from '@/lib/types';

export default function StatsPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const { overview } = useGuild();
  const [data, setData] = useState<StatsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    endpoints
      .stats(gid)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'could not load stats'));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gid]);

  // realtime command usage nudges a refresh
  const { live } = useRealtime(gid, 'command_usage', load);

  if (error) return <ErrorCard message={error} />;
  if (!data) {
    // stats-shaped skeleton: 4 stat cards + two chart blocks + table
    return (
      <div className="animate-fade-in">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-heading text-3xl">statistics</h1>
        </div>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Card key={i} className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-[12px]" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="h-6 w-1/2" />
              </div>
            </Card>
          ))}
        </div>
        <div className="mt-8 space-y-4">
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-36 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-heading text-3xl">statistics</h1>
        {live && <Badge tone="success">realtime</Badge>}
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon="sparkles" label="commands · 30d" value={nf(data.total_30d)} />
        <StatCard
          icon="sparkles"
          label="commands · 7d"
          value={nf(overview?.stats.commands_used_7d ?? 0)}
          tone="lavender"
        />
        <StatCard
          icon="heart"
          label="active users · 7d"
          value={nf(overview?.stats.active_users_7d ?? 0)}
        />
        <StatCard icon="star" label="members" value={nf(overview?.member_count)} tone="lavender" />
      </div>

      <SectionHeading icon="barChart">commands per day · 30 days</SectionHeading>
      <Card>
        <LineChart
          data={data.series.map((p) => ({ label: p.date, value: p.commands }))}
          valueLabel="commands"
          color="#FFC0CB"
        />
        {data.series.length === 0 && (
          <p className="mt-3 text-xs text-veloura-muted/70">
            recorded once the <code>command_usage</code> table exists in supabase
          </p>
        )}
      </Card>

      <SectionHeading icon="sparkles">top commands · 30 days</SectionHeading>
      <Card>
        <BarChart
          data={data.top_commands.map((t) => ({ label: t.command, value: t.count }))}
          color="#E6E6FA"
        />
      </Card>

      <SectionHeading icon="sparkles">active users per day</SectionHeading>
      <Card>
        <LineChart
          data={data.series.map((p) => ({ label: p.date, value: p.active_users }))}
          valueLabel="active users"
          color="#E6E6FA"
        />
      </Card>

      <SectionHeading icon="star">leveling leaderboard</SectionHeading>
      <Card>
        {data.leveling_leaderboard.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[400px] text-sm">
              <thead>
                <tr className="border-b border-veloura-border/60 text-left text-xs uppercase tracking-wider text-veloura-muted">
                  <th className="pb-2 pr-4">#</th>
                  <th className="pb-2 pr-4">member</th>
                  <th className="pb-2 pr-4 text-right">level</th>
                  <th className="pb-2 text-right">xp</th>
                </tr>
              </thead>
              <tbody>
                {data.leveling_leaderboard.map((row, i) => (
                  <tr key={row.user_id} className="border-b border-veloura-border/30">
                    <td className="py-3 pr-4">
                      <Badge tone={i === 0 ? 'pink' : 'muted'}>{i + 1}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-veloura-text">
                      {row.display_name ?? `user ${row.user_id}`}
                    </td>
                    <td className="py-3 pr-4 text-right text-veloura-lavender">
                      {row.level ?? '—'}
                    </td>
                    <td className="py-3 text-right text-veloura-muted">{nf(row.xp ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon="star"
            title="no leveling data yet"
            hint="xp accrues as members chat — the leaderboard wakes up on its own"
          />
        )}
      </Card>
    </div>
  );
}
