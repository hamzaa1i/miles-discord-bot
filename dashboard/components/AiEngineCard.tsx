'use client';

/**
 * components/AiEngineCard.tsx — PHASE N (Part 16).
 *
 * "AI engine" section for the guild dashboard's AI page: current route
 * diagram, provider status, model names, request counts today, GLM
 * budget meter and the sensitive-routing privacy note.
 *
 * Data comes from GET /api/dashboard/ai/status through the same-origin
 * proxy (bearer cookie, server-side only — no keys ever reach this
 * component, and the payload itself contains only sanitized metadata).
 * No giant redesign — this reuses the existing veloura cards/badges.
 */

import { useCallback, useEffect, useState } from 'react';
import { Card, CardTitle, Badge, Skeleton } from '@/components/ui/primitives';
import { Icon } from '@/components/icons';
import { api, ApiRequestError } from '@/lib/api';

interface ProviderStatus {
  configured: boolean;
  state: 'healthy' | 'cooldown' | 'degraded' | 'misconfigured' | 'unconfigured';
  models: Record<string, string>;
  today: { requests: number; successes: number; failures: number };
  last_error_category: string | null;
  cooldown_seconds_left: number;
  cooldown_reason: string;
}

interface AiStatus {
  router_enabled: boolean;
  ai_status: 'operational' | 'degraded' | 'down' | string;
  providers: Record<string, ProviderStatus>;
  routes: Record<string, { provider: string; model: string; thinking: string | null }[]>;
  openrouter: { daily_budget: number; requests_today: number };
  privacy: {
    allow_gemini_sensitive: boolean;
    allow_openrouter_sensitive: boolean;
    note: string;
  };
}

const PROVIDER_LABELS: Record<string, string> = {
  gemini: 'Gemini',
  mistral: 'Mistral',
  openrouter: 'GLM',
  groq: 'Groq',
};

const STATE_TONES: Record<string, 'success' | 'warning' | 'danger' | 'muted' | 'lavender'> = {
  healthy: 'success',
  cooldown: 'warning',
  degraded: 'warning',
  misconfigured: 'danger',
  unconfigured: 'muted',
};

const PROFILE_LABELS: { key: string; label: string; desc: string }[] = [
  { key: 'chat', label: 'normal chat', desc: 'everyday conversation & mentions' },
  { key: 'reasoning', label: 'complex reasoning', desc: 'hard questions, recaps, code' },
  { key: 'sensitive_fast', label: 'sensitive', desc: 'moderation & automod (privacy-routed)' },
];

function RouteChain({ steps }: { steps: { provider: string; model: string; thinking: string | null }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs">
      {steps.map((s, i) => (
        <span key={`${s.provider}-${s.model}-${i}`} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-veloura-muted/50" aria-hidden>↓</span>}
          <span
            className={cn(
              'rounded-full px-2.5 py-1 font-mono text-[11px]',
              s.provider === 'openrouter'
                ? 'bg-veloura-lavender/15 text-veloura-lavender'
                : 'bg-veloura-card-hover text-veloura-text',
            )}
            title={`${s.model}${s.thinking ? ` · thinking ${s.thinking}` : ''}`}
          >
            {PROVIDER_LABELS[s.provider] ?? s.provider}
          </span>
        </span>
      ))}
    </div>
  );
}

function cn(...parts: (string | false | undefined)[]) {
  return parts.filter(Boolean).join(' ');
}

export function AiEngineCard() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await api.get<AiStatus>('/ai/status');
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(
        e instanceof ApiRequestError && e.status === 401
          ? 'log in to see live ai status'
          : 'could not reach the ai status endpoint',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 30_000);
    return () => clearInterval(t);
  }, [load]);

  if (loading) {
    return (
      <Card className="mt-6 flex flex-col gap-3">
        <CardTitle icon="moon">ai engine</CardTitle>
        <Skeleton className="h-16 w-full rounded-[12px]" />
        <Skeleton className="h-16 w-full rounded-[12px]" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="mt-6">
        <CardTitle icon="moon">ai engine</CardTitle>
        <p className="mt-2 text-sm text-veloura-muted">{error}</p>
      </Card>
    );
  }

  if (!status) return null;

  const budgetUsed = status.openrouter.requests_today;
  const budgetCap = status.openrouter.daily_budget;
  const budgetPct = budgetCap > 0 ? Math.min(100, (budgetUsed / budgetCap) * 100) : 0;

  return (
    <Card className="mt-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <CardTitle icon="moon">ai engine</CardTitle>
        <div className="flex items-center gap-2">
          <Badge tone={status.ai_status === 'operational' ? 'success' : status.ai_status === 'degraded' ? 'warning' : 'danger'}>
            {status.ai_status}
          </Badge>
          {!status.router_enabled && <Badge tone="muted">groq-only mode</Badge>}
        </div>
      </div>

      {/* route diagram */}
      <div className="mt-4 space-y-4">
        {PROFILE_LABELS.map((p) => (
          <div key={p.key}>
            <p className="text-xs uppercase tracking-[0.15em] text-veloura-muted/70">
              {p.label}
              <span className="ml-2 normal-case tracking-normal text-veloura-muted/50">
                {p.desc}
              </span>
            </p>
            <div className="mt-1.5">
              <RouteChain steps={status.routes[p.key] ?? []} />
            </div>
          </div>
        ))}
      </div>

      {/* provider status rows */}
      <div className="mt-5 space-y-1.5">
        <p className="text-xs uppercase tracking-[0.15em] text-veloura-muted/70">providers</p>
        {Object.entries(status.providers).map(([name, p]) => (
          <div
            key={name}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[10px] px-2.5 py-2 text-sm hover:bg-veloura-card-hover/40"
          >
            <span className="w-20 shrink-0 text-veloura-text">{PROVIDER_LABELS[name] ?? name}</span>
            <Badge tone={STATE_TONES[p.state] ?? 'muted'}>
              {p.state === 'unconfigured' ? 'off' : p.state}
            </Badge>
            {p.configured && p.today.requests > 0 && (
              <span className="text-xs text-veloura-muted">
                {p.today.requests} req today · {p.today.successes}✓ / {p.today.failures}✗
              </span>
            )}
            {p.cooldown_seconds_left > 0 && (
              <span className="text-xs text-veloura-warning">
                cooldown {p.cooldown_seconds_left}s
              </span>
            )}
            {name === 'openrouter' && p.configured && budgetCap > 0 && (
              <span className="text-xs text-veloura-muted">
                {budgetUsed} / {budgetCap} today
              </span>
            )}
          </div>
        ))}
      </div>

      {/* GLM budget meter */}
      {budgetCap > 0 && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-veloura-muted">
            <span>glm reasoning budget (today)</span>
            <span className={budgetPct >= 100 ? 'text-veloura-warning' : ''}>
              {budgetUsed} / {budgetCap}
            </span>
          </div>
          <div
            className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-veloura-border/60"
            role="meter"
            aria-valuenow={budgetUsed}
            aria-valuemin={0}
            aria-valuemax={budgetCap}
            aria-label="openrouter daily requests used"
          >
            <div
              className={cn(
                'h-full rounded-full transition-all',
                budgetPct >= 100 ? 'bg-veloura-warning' : 'bg-veloura-lavender',
              )}
              style={{ width: `${budgetPct}%` }}
            />
          </div>
          {budgetPct >= 100 && (
            <p className="mt-1.5 text-xs text-veloura-muted">
              budget reached — reasoning traffic fails over to the next provider until tomorrow (utc)
            </p>
          )}
        </div>
      )}

      {/* privacy note */}
      <div className="mt-5 rounded-[12px] border border-veloura-lavender/20 bg-veloura-lavender/5 p-3.5">
        <p className="flex items-center gap-2 text-xs font-medium text-veloura-lavender">
          <Icon name="shield" size={13} />
          privacy routing
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-veloura-muted">
          sensitive requests (moderation, automod) route mistral → groq by
          default — gemini and openrouter only join sensitive routes when
          explicitly enabled
          {status.privacy.allow_gemini_sensitive ? ' (gemini: on)' : ' (gemini: off)'}
          {status.privacy.allow_openrouter_sensitive ? ' (glm: on)' : ' (glm: off)'}.
          /privacy opt-outs are enforced before any provider is invoked, and
          provider telemetry stores counts and latencies — never
          conversations.
        </p>
      </div>
    </Card>
  );
}
