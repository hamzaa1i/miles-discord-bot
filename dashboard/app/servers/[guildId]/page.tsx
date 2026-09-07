'use client';

/** Overview — server heartbeat: stats, features, quick actions, activity feed. */

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useGuild } from '@/lib/guild';
import { endpoints, ApiRequestError } from '@/lib/api';
import { StatCard, SectionHeading, EmptyState } from '@/components/EmptyState';
import { Card, CardTitle, Badge, LoadingCard } from '@/components/ui/primitives';
import { AuditList } from '@/components/AuditList';
import { BarChart } from '@/components/StatsChart';
import { useToast } from '@/components/ui/toast';
import { useRealtime } from '@/lib/useRealtime';
import { nf, timeAgo } from '@/lib/format';

const FEATURE_ROUTES: Record<string, { label: string; href: string }> = {
  welcome: { label: 'welcome', href: 'welcome' },
  leveling: { label: 'leveling', href: 'leveling' },
  qotd: { label: 'qotd', href: 'qotd' },
  ai_automod: { label: 'ai automod', href: 'automod' },
  starboard: { label: 'starboard', href: 'starboard' },
  logging: { label: 'logging', href: 'logging' },
  confessions: { label: 'confessions', href: 'confessions' },
  proactive: { label: 'proactive', href: 'ai' },
  onboarding: { label: 'onboarding', href: 'roles' },
  nick: { label: 'nickname requests', href: 'nick' },
  birthdays: { label: 'birthdays', href: 'birthdays' },
  custom_commands: { label: 'custom commands', href: 'custom-commands' },
  self_roles: { label: 'self roles', href: 'roles' },
  giveaways: { label: 'giveaways', href: 'giveaways' },
};

export default function OverviewPage() {
  const { guildId, overview, audit, loading, error, reloadAudit, reloadOverview } = useGuild();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  // realtime: new command usage / warnings refresh the overview quietly
  const { live } = useRealtime(guildId, 'command_usage', () => {
    void reloadOverview();
  });

  useEffect(() => {
    void reloadAudit();
  }, [reloadAudit]);

  async function runAction(action: string, label: string, params: Record<string, unknown> = {}) {
    setBusy(action);
    try {
      await endpoints.action(guildId, action, params);
      toast.push(`${label} queued — the bot acts within ~5s ✦`, 'success');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'action failed', 'error');
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingCard label="reading the stars…" />
        <LoadingCard />
      </div>
    );
  }

  if (error || !overview) {
    return (
      <Card className="border-veloura-danger/30">
        <p className="text-sm text-veloura-danger">✧ {error ?? 'could not load overview'}</p>
        <button className="veloura-button-ghost mt-4" onClick={() => window.location.reload()}>
          retry
        </button>
      </Card>
    );
  }

  const stats = overview.stats;

  return (
    <div className="animate-fade-in">
      {/* stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon="heart" label="members" value={nf(overview.member_count)} />
        <StatCard icon="sparkles" label="online" value={nf(overview.online_count)} tone="lavender" />
        <StatCard icon="bell" label="boosts" value={overview.boost_count} />
        <StatCard
          icon="sparkles"
          label="commands · 7d"
          value={nf(stats.commands_used_7d)}
          sub={`${nf(stats.active_users_7d)} active souls`}
        />
      </div>

      {/* quick actions */}
      <SectionHeading icon="sparkles">quick actions</SectionHeading>
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="flex flex-col gap-3">
          <CardTitle icon="helpCircle">post qotd now</CardTitle>
          <p className="flex-1 text-xs leading-relaxed text-veloura-muted">
            send today&apos;s question immediately, no waiting for the scheduled hour.
          </p>
          <button
            disabled={busy !== null}
            onClick={() => runAction('qotd_post_now', 'qotd post')}
            className="veloura-button-ghost !min-h-[40px] text-xs"
          >
            {busy === 'qotd_post_now' ? 'queuing…' : 'post now'}
          </button>
        </Card>
        <Card className="flex flex-col gap-3">
          <CardTitle icon="heart">test welcome</CardTitle>
          <p className="flex-1 text-xs leading-relaxed text-veloura-muted">
            send the current welcome card to its channel with you as the guest.
          </p>
          <button
            disabled={busy !== null}
            onClick={() => runAction('welcome_test', 'welcome test', { type: 'welcome' })}
            className="veloura-button-ghost !min-h-[40px] text-xs"
          >
            {busy === 'welcome_test' ? 'queuing…' : 'send test'}
          </button>
        </Card>
        <Card className="flex flex-col gap-3">
          <CardTitle icon="bell">refresh data</CardTitle>
          <p className="flex-1 text-xs leading-relaxed text-veloura-muted">
            purge cached settings so the bot re-reads them from the database.
          </p>
          <button
            disabled={busy !== null}
            onClick={() => runAction('purge_cache', 'cache purge')}
            className="veloura-button-ghost !min-h-[40px] text-xs"
          >
            {busy === 'purge_cache' ? 'queuing…' : 'purge cache'}
          </button>
        </Card>
      </div>

      {/* active features */}
      <SectionHeading icon="sparkles" right={live ? <Badge tone="success">realtime</Badge> : undefined}>
        active features
      </SectionHeading>
      <Card>
        <div className="flex flex-wrap gap-2">
          {Object.entries(FEATURE_ROUTES).map(([key, meta]) => {
            const on = overview.active_features[key];
            return (
              <Link
                key={key}
                href={`/servers/${guildId}/${meta.href}`}
                className="transition hover:scale-[1.03]"
              >
                <Badge tone={on ? 'pink' : 'muted'}>
                  {on ? '✦' : '○'} {meta.label}
                </Badge>
              </Link>
            );
          })}
        </div>
        {Object.values(overview.active_features).every((v) => !v) && (
          <p className="mt-3 text-sm text-veloura-muted/70">
            everything is asleep — enable a module below to wake it ✧
          </p>
        )}
      </Card>

      {/* top commands */}
      <SectionHeading icon="barChart">top commands · 7d</SectionHeading>
      <Card>
        {stats.top_commands.length > 0 ? (
          <BarChart data={stats.top_commands.map((t) => ({ label: t.command, value: t.count }))} />
        ) : (
          <EmptyState
            icon="sparkles"
            title="no commands used this week"
            hint="slash command usage is recorded automatically once the command_usage table exists in supabase"
          />
        )}
      </Card>

      {/* activity feed */}
      <SectionHeading icon="scroll">dashboard activity</SectionHeading>
      <Card>
        <AuditList entries={audit} limit={10} />
      </Card>

      <p className="mt-8 text-center text-xs text-veloura-muted/50">
        aurelia joined this server {overview.bot_joined_at ? timeAgo(overview.bot_joined_at) : '—'} ·{' '}
        <span className="twinkle" aria-hidden>
          ✦
        </span>
      </p>
    </div>
  );
}
