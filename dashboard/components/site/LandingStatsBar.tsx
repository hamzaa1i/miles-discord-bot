'use client';

/**
 * components/site/LandingStatsBar.tsx — PHASE M PART 1 §2.
 *
 * Live stats strip for the landing hero: total servers, members served,
 * uptime percentage and commands available. Auto-refreshes every 60s
 * from the bot's public /health endpoint (NEXT_PUBLIC_API_URL).
 *
 * Every number degrades gracefully: while loading (skeleton dots), when
 * the bot is offline ("—"), and the uptime percentage comes from the
 * /api/public/stats history samples (shows "fresh" while young).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/format';
import { nf } from '@/lib/format';
import { COMMAND_COUNT } from '@/lib/marketing';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080').replace(/\/$/, '');
const POLL_MS = 60_000;
const FETCH_TIMEOUT_MS = 10_000;

type Health = {
  status?: string;
  guilds?: number;
  users?: number;
  latency_ms?: number;
  uptime_seconds?: number;
};

type PublicStats = {
  uptime_percent?: number | null;
};

type Cell = { label: string; value: string; hint?: string };

export function LandingStatsBar({ className }: { className?: string }) {
  const [cells, setCells] = useState<Cell[] | null>(null);
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

      const [health, stats] = await Promise.all([
        withTimeout(
          fetch(`${API_BASE}/health`, { cache: 'no-store' })
            .then((r) => (r.ok ? (r.json() as Promise<Health>) : Promise.reject(new Error('bad status'))))
            .catch(() => null),
        ),
        withTimeout(
          fetch(`${API_BASE}/api/public/stats`, { cache: 'no-store' })
            .then((r) => (r.ok ? (r.json() as Promise<PublicStats>) : Promise.reject(new Error('bad status'))))
            .catch(() => null),
        ),
      ]);

      if (!health) {
        setCells([
          { label: 'servers', value: '—' },
          { label: 'members served', value: '—' },
          { label: 'uptime', value: '—' },
          { label: 'commands', value: String(COMMAND_COUNT), hint: 'always available ✦' },
        ]);
        return;
      }

      const upPct = stats?.uptime_percent;
      const d = Math.floor((health.uptime_seconds ?? 0) / 86400);
      setCells([
        { label: 'servers', value: nf(health.guilds ?? 0) },
        { label: 'members served', value: nf(health.users ?? 0) },
        {
          label: 'uptime',
          value: upPct != null ? `${upPct}%` : d >= 1 ? `${d} day${d === 1 ? '' : 's'}` : 'fresh',
        },
        { label: 'commands', value: nf(COMMAND_COUNT) },
      ]);
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

  return (
    <dl
      aria-label="live bot statistics"
      className={cn(
        'grid w-full max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4',
        className,
      )}
    >
      {(cells ?? Array.from({ length: 4 }, () => null)).map((cell, i) => (
        <div
          key={cell?.label ?? i}
          className="veloura-card flex flex-col items-center gap-0.5 px-4 py-3"
        >
          {cell ? (
            <>
              <dd className="font-heading text-2xl text-veloura-pink">{cell.value}</dd>
              <dt className="text-[11px] uppercase tracking-wider text-veloura-muted/80">
                {cell.label}
              </dt>
            </>
          ) : (
            <>
              <div className="animate-pulse-soft h-7 w-14 rounded-[8px] bg-veloura-card-hover" />
              <div className="animate-pulse-soft h-2.5 w-16 rounded-[6px] bg-veloura-card-hover" />
            </>
          )}
        </div>
      ))}
    </dl>
  );
}
