'use client';

/**
 * ModuleCard — the standard page header for module pages:
 * icon + title + description + big enable toggle.
 */

import { ToggleSwitch } from './ToggleSwitch';

export function ModuleCard({
  icon,
  title,
  description,
  enabled,
  onToggle,
  toggledLabel = 'enabled',
  children,
}: {
  icon: string;
  title: string;
  description: string;
  enabled?: boolean;
  onToggle?: (next: boolean) => void;
  toggledLabel?: string;
  children: React.ReactNode;
}) {
  const hasToggle = enabled !== undefined && onToggle !== undefined;

  return (
    <div className="veloura-card mb-6 overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-veloura-border/60 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <div
            aria-hidden
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[12px] bg-veloura-navy text-2xl shadow-glow"
          >
            {icon}
          </div>
          <div>
            <h1 className="font-heading text-2xl text-veloura-text">{title}</h1>
            <p className="mt-1 text-sm text-veloura-muted">{description}</p>
          </div>
        </div>
        {hasToggle && (
          <div className="flex shrink-0 items-center gap-3">
            <span className="text-xs uppercase tracking-wider text-veloura-muted">
              {enabled ? toggledLabel : 'disabled'}
            </span>
            <ToggleSwitch checked={enabled} onChange={onToggle} size="lg" label={`toggle ${title}`} />
          </div>
        )}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}
