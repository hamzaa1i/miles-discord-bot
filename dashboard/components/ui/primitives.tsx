'use client';

/** Field primitives: labeled input / textarea / select / switch / badge / card / skeleton / tabs. */

import React from 'react';
import { cn } from '@/lib/format';
import { MaybeIcon, Icon } from '@/components/icons';

export function Card({
  children,
  className,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('veloura-card p-5', className)} {...rest}>
      {children}
    </div>
  );
}

export function CardTitle({ children, icon }: { children: React.ReactNode; icon?: string }) {
  return (
    <h3 className="flex items-center gap-2.5 font-heading text-lg text-veloura-text">
      {icon && <MaybeIcon value={icon} size={17} className="text-veloura-pink" />}
      {children}
    </h3>
  );
}

export function Field({
  label,
  help,
  children,
  htmlFor,
}: {
  label?: string;
  help?: string;
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="mb-4 last:mb-0">
      {label && (
        <label htmlFor={htmlFor} className="veloura-label">
          {label}
        </label>
      )}
      {children}
      {help && <p className="mt-1.5 text-xs leading-relaxed text-veloura-muted/80">{help}</p>}
    </div>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn('veloura-input', props.className)} />;
}

export const TextArea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function TextArea(props, ref) {
  return <textarea ref={ref} {...props} className={cn('veloura-input resize-y', props.className)} />;
});

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={cn('veloura-input appearance-none pr-8', props.className)} />
  );
}

export function Badge({
  children,
  tone = 'default',
  className,
}: {
  children: React.ReactNode;
  tone?: 'default' | 'pink' | 'lavender' | 'success' | 'danger' | 'muted';
  className?: string;
}) {
  const tones: Record<string, string> = {
    default: 'border-veloura-border text-veloura-muted',
    pink: 'border-veloura-pink/40 bg-veloura-pink/10 text-veloura-pink',
    lavender: 'border-veloura-lavender/40 bg-veloura-lavender/10 text-veloura-lavender',
    success: 'border-veloura-success/40 bg-veloura-success/10 text-veloura-success',
    danger: 'border-veloura-danger/40 bg-veloura-danger/10 text-veloura-danger',
    muted: 'border-transparent bg-veloura-card-hover text-veloura-muted',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse-soft rounded-[12px] bg-veloura-card-hover', className)} />;
}

export function LoadingCard({ label = 'loading…' }: { label?: string }) {
  return (
    <Card>
      <div className="flex items-center gap-3 text-sm text-veloura-muted">
        <Icon name="refresh" size={15} className="twinkle text-veloura-lavender" />
        {label}
      </div>
      <div className="mt-4 space-y-3">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-4/5" />
        <Skeleton className="h-9 w-3/5" />
      </div>
    </Card>
  );
}

export function ErrorCard({ message, action }: { message: string; action?: React.ReactNode }) {
  return (
    <Card className="border-veloura-danger/30">
      <div className="flex flex-col items-start gap-3">
        <p className="flex items-center gap-2 text-sm text-veloura-danger">
          <Icon name="shieldAlert" size={15} />
          {message}
        </p>
        {action}
      </div>
    </Card>
  );
}

/* ── Tabs (uncontrolled, hash-free) ───────────────────────────── */

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string; icon?: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div role="tablist" className="mb-6 flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            'min-h-[44px] rounded-[12px] border px-4 py-2 text-sm transition',
            active === t.id
              ? 'border-veloura-pink/60 bg-veloura-pink/10 text-veloura-pink shadow-glow'
              : 'border-veloura-border text-veloura-muted hover:border-veloura-lavender/40 hover:text-veloura-text',
          )}
        >
          {t.icon && <MaybeIcon value={t.icon} size={14} className="mr-1.5 inline-block align-[-2px]" />}
          {t.label}
        </button>
      ))}
    </div>
  );
}
