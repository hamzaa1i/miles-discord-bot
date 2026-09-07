'use client';

/** EmptyState + StatCard + SectionHeading — small shared layout bits. */

import { cn } from '@/lib/format';

export function EmptyState({
  icon = '✧',
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-veloura-border/70 px-6 py-10 text-center">
      <div aria-hidden className="mb-3 text-3xl text-veloura-lavender/60">
        {icon}
      </div>
      <p className="text-sm text-veloura-muted">{title}</p>
      {hint && <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-veloura-muted/60">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function StatCard({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: string;
  label: string;
  value: string | number;
  sub?: string;
  tone?: 'pink' | 'lavender';
}) {
  return (
    <div className="veloura-card p-4 transition hover:border-veloura-lavender/30">
      <div className="flex items-center gap-3">
        <div
          aria-hidden
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-[12px] text-lg',
            tone === 'lavender' ? 'bg-veloura-lavender/10' : 'bg-veloura-pink/10',
          )}
        >
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wider text-veloura-muted/80">{label}</p>
          <p className="font-heading text-2xl leading-tight text-veloura-text">{value}</p>
          {sub && <p className="truncate text-xs text-veloura-muted/70">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

export function SectionHeading({
  icon,
  children,
  right,
}: {
  icon?: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-4 mt-8 flex items-center justify-between first:mt-0">
      <h2 className="flex items-center gap-2 font-heading text-xl text-veloura-text">
        {icon && <span aria-hidden>{icon}</span>}
        {children}
      </h2>
      {right}
    </div>
  );
}
