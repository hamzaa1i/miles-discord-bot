'use client';

/**
 * app/stats/page.tsx — PHASE M PART 4 — the public stats page.
 *
 * No login. Polls the public endpoints every 30s:
 *   · /api/public/stats  — usage, fun counters, growth + latency history
 *   · /health            — live vitals for the status pill
 *
 * Charts reuse the dashboard's dependency-free SVG components
 * (LineChart / BarChart). Every section degrades gracefully when the
 * backend is asleep (Render free tier) — skeletons, then "—" values.
 */

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import { BarChart, LineChart, Point } from '@/components/StatsChart';
import { Icon } from '@/components/icons';
import { ShareButtons } from '@/components/site/ShareButtons';
import { SiteFooter } from '@/components/site/SiteFooter';
import { SiteHeader } from '@/components/site/SiteHeader';
import { cn } from '@/lib/format';
import { nf } from '@/lib/format';
import { COMMAND_COUNT, SUPPORT_SERVER_URL } from '@/lib/marketing';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080').replace(/\/$/, '');
const POLL_MS = 30_000;
const FETCH_TIMEOUT_MS = 10_000;

type PublicStats = {
  status?: string;
  version?: string;
  servers?: number;
  members?: number;
  latency_ms?: number;
  uptime_seconds?: number;
  uptime_percent?: number | null;
  avg_response_ms?: number;
  commands_used_today?: number | null;
  top_commands?: { command: string; count: number }[];
  fun_stats?: {
    total_xp?: number | null;
    warnings_issued?: number | null;
    confessions_posted?: number | null;
    memories_stored?: number | null;
    daily_streaks_active?: number | null;
  };
  growth?: { date: string; servers: number; members: number }[];
  latency_history?: { t: number; latency_ms: number }[];
};

type Health = { status?: string; latency_ms?: number };

function humanUptime(s: number): string {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d >= 1) return `${d}d ${h}h`;
  if (h >= 1) return `${h}h ${m}m`;
  if (m >= 1) return `${m}m`;
  return 'just woke up';
}

function shortTime(t: number): string {
  return new Date(t * 1000).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function StatsClient() {
  const [stats, setStats] = useState<PublicStats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);
  const inFlight = useRef(false);

  const poll = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const withTimeout = <T,>(p: Promise<T>): Promise<T> =>
        Promise.race([
          p,
          new Promise<T>((_, rej) => setTimeout(() => rej(new Error('timeout')), FETCH_TIMEOUT_MS)),
        ]);

      const [s, h] = await Promise.all([
        withTimeout(
          fetch(`${API_BASE}/api/public/stats`, { cache: 'no-store' })
            .then((r) => (r.ok ? (r.json() as Promise<PublicStats>) : null))
            .catch(() => null),
        ),
        withTimeout(
          fetch(`${API_BASE}/health`, { cache: 'no-store' })
            .then((r) => (r.ok ? (r.json() as Promise<Health>) : null))
            .catch(() => null),
        ),
      ]);
      setOffline(s === null);
      if (s) setStats(s);
      if (h) setHealth(h);
      setCheckedAt(Date.now());
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    poll();
    const t = setInterval(poll, POLL_MS);
    const onVis = () => {
      if (document.visibilityState === 'visible') poll();
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      clearInterval(t);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [poll]);

  const status: 'ok' | 'degraded' | 'down' | 'loading' =
    !stats && !health
      ? 'loading'
      : offline
        ? 'down'
        : health?.status === 'ok' && (health.latency_ms ?? 0) < 500
          ? 'ok'
          : 'degraded';

  const statusMeta = {
    loading: { label: 'checking…', color: 'text-veloura-muted' },
    ok: { label: 'operational ♡', color: 'text-veloura-success' },
    degraded: { label: 'degraded ✦', color: 'text-[#F5D68A]' },
    down: { label: 'waking up ✧', color: 'text-veloura-danger' },
  }[status];

  const growthPoints: Point[] = (stats?.growth ?? []).map((g) => ({
    label: g.date,
    value: g.servers,
  }));
  const latencyPoints: Point[] = (stats?.latency_history ?? []).map((l) => ({
    label: shortTime(l.t),
    value: l.latency_ms,
  }));
  const topCommands: Point[] = (stats?.top_commands ?? []).map((c) => ({
    label: c.command,
    value: c.count,
  }));

  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <header className="mb-10">
          <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">public stats</p>
          <h1 className="font-heading mt-2 text-4xl text-veloura-text">her vitals, live ✦</h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
            aggregated and anonymized — server counts, command usage and the
            fun counters. refreshes every 30 seconds; charts build from the
            history samples.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            <span
              aria-live="polite"
              className={cn('flex items-center gap-2 text-sm font-medium', statusMeta.color)}
            >
              <span className={cn('pulse-glow inline-block h-2.5 w-2.5 rounded-full bg-current')} aria-hidden />
              {statusMeta.label}
            </span>
            {checkedAt && (
              <span className="text-xs text-veloura-muted/60">
                checked {Math.max(0, Math.round((Date.now() - checkedAt) / 1000))}s ago
              </span>
            )}
            <ShareButtons compact className="no-print" text="aurelia's live stats — the softest discord bot ✦" />
          </div>
        </header>

        {/* ══ 1 · real-time ════════════════════════════════════════ */}
        <section aria-label="real-time statistics" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="servers" value={stats ? nf(stats.servers ?? 0) : null} icon="sparkles" />
          <StatCard label="members" value={stats ? nf(stats.members ?? 0) : null} icon="users" />
          <StatCard
            label="commands today"
            value={stats?.commands_used_today != null ? nf(stats.commands_used_today) : null}
            icon="wand"
          />
          <StatCard
            label="latency"
            value={health ? `${Math.round(health.latency_ms ?? 0)}ms` : null}
            icon="zap"
          />
        </section>

        {/* ══ 2 · uptime & performance ═════════════════════════════ */}
        <section aria-label="uptime and performance" className="mt-10">
          <h2 className="font-heading text-2xl text-veloura-text">uptime & performance</h2>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <div className="veloura-card p-5 lg:col-span-1">
              <p className="text-[11px] uppercase tracking-wider text-veloura-muted/70">current uptime</p>
              <p className="font-heading mt-1 text-2xl text-veloura-text">
                {stats ? humanUptime(stats.uptime_seconds ?? 0) : '—'}
              </p>
              <p className="mt-3 text-[11px] uppercase tracking-wider text-veloura-muted/70">
                30-day availability
              </p>
              <p className="font-heading mt-1 text-2xl text-veloura-text">
                {stats?.uptime_percent != null ? `${stats.uptime_percent}%` : 'building…'}
              </p>
              <p className="mt-3 text-[11px] leading-relaxed text-veloura-muted/60">
                samples are recorded every 10 minutes — the percentage
                becomes meaningful after a day of history ♡
              </p>
            </div>
            <div className="veloura-card p-5 lg:col-span-2">
              <p className="mb-2 text-[11px] uppercase tracking-wider text-veloura-muted/70">
                response time (10-min samples)
              </p>
              <LineChart data={latencyPoints} valueLabel="latency (ms)" height={180} />
            </div>
          </div>
        </section>

        {/* ══ 3 · feature usage ════════════════════════════════════ */}
        <section aria-label="feature usage" className="mt-10 grid gap-4 lg:grid-cols-2">
          <div className="veloura-card p-5">
            <h2 className="font-heading text-xl text-veloura-text">top commands · 7 days</h2>
            <p className="mt-1 text-xs text-veloura-muted/70">command names and counts only — anonymized by design</p>
            <div className="mt-4">
              <BarChart data={topCommands} max={20} />
            </div>
          </div>
          <div className="veloura-card p-5">
            <h2 className="font-heading text-xl text-veloura-text">growth · servers over time</h2>
            <p className="mt-1 text-xs text-veloura-muted/70">one point per day from the history samples</p>
            <div className="mt-4">
              <LineChart data={growthPoints} valueLabel="servers" height={180} />
            </div>
          </div>
        </section>

        {/* ══ 4 · fun stats ════════════════════════════════════════ */}
        <section aria-label="fun statistics" className="mt-10">
          <h2 className="font-heading text-2xl text-veloura-text">fun stats ✧</h2>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StatCard label="total xp" value={val(stats?.fun_stats?.total_xp)} icon="star" />
            <StatCard label="warnings" value={val(stats?.fun_stats?.warnings_issued)} icon="swords" />
            <StatCard label="confessions" value={val(stats?.fun_stats?.confessions_posted)} icon="moon" />
            <StatCard label="memories" value={val(stats?.fun_stats?.memories_stored)} icon="heart" />
            <StatCard label="active streaks" value={val(stats?.fun_stats?.daily_streaks_active)} icon="gift" />
          </div>
        </section>

        {/* ══ 5 · version info ═════════════════════════════════════ */}
        <section aria-label="version information" className="mt-10">
          <h2 className="font-heading text-2xl text-veloura-text">version</h2>
          <div className="veloura-card mt-4 flex flex-wrap items-center justify-between gap-4 p-5">
            <div>
              <p className="font-heading text-2xl text-veloura-pink">
                {stats?.version ?? '—'}
              </p>
              <p className="mt-1 text-xs text-veloura-muted/70">
                {COMMAND_COUNT} commands · see what changed in every release
              </p>
            </div>
            <Link href="/changelog" className="veloura-button-ghost px-5 text-sm">
              view full changelog
              <span aria-hidden>→</span>
            </Link>
          </div>
          <p className="mt-4 text-xs leading-relaxed text-veloura-muted/60">
            something look wrong?{' '}
            {SUPPORT_SERVER_URL ? (
              <a href={SUPPORT_SERVER_URL} target="_blank" rel="noopener noreferrer" className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
                tell us in the support server
              </a>
            ) : (
              'let us know in the support server'
            )}
            .
          </p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

function val(v: number | null | undefined): string | null {
  return v == null ? null : nf(v);
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | null;
  icon: string;
}) {
  return (
    <div className="veloura-card p-4 sm:p-5">
      <div className="flex items-center gap-2 text-veloura-muted/70">
        <Icon name={icon} size={14} />
        <p className="text-[11px] uppercase tracking-wider">{label}</p>
      </div>
      {value === null ? (
        <div className="animate-pulse-soft mt-2 h-7 w-16 rounded-[8px] bg-veloura-card-hover" />
      ) : (
        <p className="font-heading mt-1.5 text-2xl text-veloura-text">{value}</p>
      )}
    </div>
  );
}
