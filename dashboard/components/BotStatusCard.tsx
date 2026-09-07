'use client';

/**
 * components/BotStatusCard.tsx — live bot health card for the landing page.
 *
 * Polls the Flask /health endpoint (NEXT_PUBLIC_API_URL) every 30 seconds
 * and renders the bot's vitals in the veloura aesthetic:
 *
 *   ● online ♡        (green, health OK)
 *   ● reconnecting ✦  (yellow, latency > 500ms or bot still starting)
 *   ● offline ✧       (red, /health unreachable — "aurelia is resting ♡")
 *
 * All text is lowercase; the status dot glows softly (pulseGlow keyframe,
 * globals.css). Polling pauses while the tab is hidden and resumes (with an
 * immediate refresh) when it becomes visible again.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Circle } from 'lucide-react';
import { cn } from '@/lib/format';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080').replace(/\/$/, '');
const HEALTH_URL = `${API_BASE}/health`;
const POLL_MS = 30_000;
const FETCH_TIMEOUT_MS = 12_000;
const SLOW_LATENCY_MS = 500;

type HealthBody = {
  status?: string;
  uptime_seconds?: number;
  uptime_human?: string;
  guilds?: number;
  users?: number;
  latency_ms?: number;
  active_cogs?: number;
};

type Phase = 'loading' | 'online' | 'waking' | 'reconnecting' | 'offline';

type Snapshot = {
  phase: Exclude<Phase, 'loading'>;
  uptimeSeconds: number;
  servers: number;
  members: number;
  latencyMs: number;
  checkedAt: number; // Date.now() of the last completed check
};

const PHASE_META: Record<Exclude<Phase, 'loading'>, { label: string; color: string }> = {
  online: { label: 'online ♡', color: '#A8E6CF' },
  waking: { label: 'waking up ✦', color: '#F5D68A' },
  reconnecting: { label: 'reconnecting ✦', color: '#F5D68A' },
  offline: { label: 'offline ✧', color: '#F4A8A8' },
};

/** "3 days" · "5 hours" · "12 minutes" · "just woke up" */
function humanUptime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const h = Math.floor(seconds / 3600);
  const d = Math.floor(seconds / 86400);
  if (d >= 1) return `${d} day${d === 1 ? '' : 's'}`;
  if (h >= 1) return `${h} hour${h === 1 ? '' : 's'}`;
  if (m >= 1) return `${m} minute${m === 1 ? '' : 's'}`;
  return 'just woke up';
}

function plural(n: number, unit: 'second' | 'minute'): string {
  if (unit === 'minute') return `${n} minute${n === 1 ? '' : 's'}`;
  return `${n} second${n === 1 ? '' : 's'}`;
}

async function fetchHealth(): Promise<HealthBody> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(HEALTH_URL, { cache: 'no-store', signal: ctrl.signal });
    if (!res.ok) throw new Error(`health ${res.status}`);
    return (await res.json()) as HealthBody;
  } finally {
    clearTimeout(timer);
  }
}

function classify(body: HealthBody): Exclude<Phase, 'loading'> {
  if ((body.latency_ms ?? 0) > SLOW_LATENCY_MS) return 'reconnecting';
  if (body.status === 'ok') return 'online';
  if (body.status === 'starting') return 'waking';
  return 'offline';
}

export default function BotStatusCard({ className }: { className?: string }) {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());
  const inFlight = useRef(false);

  const poll = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const body = await fetchHealth();
      const phase = classify(body);
      setSnap({
        phase: phase === 'offline' ? 'offline' : phase,
        uptimeSeconds: body.uptime_seconds ?? 0,
        servers: body.guilds ?? 0,
        members: body.users ?? 0,
        latencyMs: body.latency_ms ?? 0,
        checkedAt: Date.now(),
      });
    } catch {
      // fetch error, timeout, non-200 or bad JSON — same gentle state
      setSnap({
        phase: 'offline',
        uptimeSeconds: 0,
        servers: 0,
        members: 0,
        latencyMs: 0,
        checkedAt: Date.now(),
      });
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    poll();
    const pollTimer = setInterval(poll, POLL_MS);

    // 1s tick only drives the "last checked X seconds ago" line
    const tick = setInterval(() => setNow(Date.now()), 1000);

    // don't poll in a hidden tab; refresh immediately on return
    const onVisibility = () => {
      if (document.visibilityState === 'visible') poll();
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      clearInterval(pollTimer);
      clearInterval(tick);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [poll]);

  const meta = snap ? PHASE_META[snap.phase] : null;

  return (
    <div
      aria-live="polite"
      className={cn(
        'veloura-card relative w-full max-w-md rounded-card border-veloura-pink/25 p-5',
        'animate-fade-in',
        className,
      )}
    >
      {/* faint pink glow along the top edge */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-6 -top-px h-px bg-gradient-to-r from-transparent via-veloura-pink/40 to-transparent"
      />

      {/* row 1 — status indicator */}
      {snap && meta ? (
        <div className="flex items-center gap-3">
          <span className="relative flex h-4 w-4 items-center justify-center" aria-hidden>
            <Circle
              size={10}
              className="pulse-glow"
              fill={meta.color}
              color={meta.color}
              strokeWidth={0}
            />
          </span>
          <p className="text-sm font-medium tracking-wide" style={{ color: meta.color }}>
            {meta.label}
          </p>
          {snap.phase === 'offline' && (
            <p className="ml-auto text-xs text-veloura-muted/80">aurelia is resting ♡</p>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <div className="animate-pulse-soft h-2.5 w-2.5 rounded-full bg-veloura-muted/40" />
          <div className="animate-pulse-soft h-4 w-24 rounded-[8px] bg-veloura-card-hover" />
        </div>
      )}

      {/* row 2 — vitals grid (2 cols mobile / 4 cols desktop) */}
      <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        {snap && snap.phase !== 'offline' ? (
          <>
            <Stat label="uptime" value={humanUptime(snap.uptimeSeconds)} />
            <Stat label="servers" value={String(snap.servers)} />
            <Stat label="members" value={snap.members.toLocaleString()} />
            <Stat label="latency" value={`${Math.round(snap.latencyMs)}ms`} />
          </>
        ) : snap ? (
          <>
            <Stat label="uptime" value="—" muted />
            <Stat label="servers" value="—" muted />
            <Stat label="members" value="—" muted />
            <Stat label="latency" value="—" muted />
          </>
        ) : (
          [0, 1, 2, 3].map((i) => (
            <div key={i} className="space-y-1.5">
              <div className="animate-pulse-soft h-2.5 w-12 rounded-[6px] bg-veloura-card-hover" />
              <div className="animate-pulse-soft h-4 w-14 rounded-[8px] bg-veloura-card-hover" />
            </div>
          ))
        )}
      </div>

      {/* row 3 — last checked */}
      <p className="mt-4 border-t border-veloura-border/60 pt-3 text-[11px] leading-none text-veloura-muted/60">
        {snap ? (
          <>
            last checked{' '}
            {now - snap.checkedAt < 5
              ? 'just now'
              : now - snap.checkedAt < 60_000
                ? plural(Math.floor((now - snap.checkedAt) / 1000), 'second')
                : plural(Math.floor((now - snap.checkedAt) / 60_000), 'minute')}{' '}
            ago ✧
          </>
        ) : (
          'checking on aurelia ✧'
        )}
      </p>
    </div>
  );
}

function Stat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-veloura-muted/70">{label}</p>
      <p className={cn('mt-0.5 text-sm font-medium', muted ? 'text-veloura-muted/50' : 'text-veloura-text')}>
        {value}
      </p>
    </div>
  );
}
