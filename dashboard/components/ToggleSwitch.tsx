'use client';

/** ToggleSwitch — the veloura on/off pill used at the top of module pages. */

import { cn } from '@/lib/format';

export function ToggleSwitch({
  checked,
  onChange,
  label,
  disabled,
  size = 'md',
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: string;
  disabled?: boolean;
  size?: 'md' | 'lg';
}) {
  const dims = size === 'lg' ? { w: 'w-14', h: 'h-7', knob: 'h-6 w-6', travel: 'translate-x-7' } : { w: 'w-11', h: 'h-6', knob: 'h-5 w-5', travel: 'translate-x-5' };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label ?? 'toggle'}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex shrink-0 items-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-veloura-pink/40 disabled:opacity-50',
        dims.w,
        dims.h,
        checked
          ? 'border-veloura-pink/60 bg-veloura-pink/25 shadow-glow'
          : 'border-veloura-border bg-veloura-navy',
      )}
    >
      <span
        aria-hidden
        className={cn(
          'absolute left-0.5 rounded-full transition-transform duration-200',
          dims.knob,
          checked ? `${dims.travel} bg-veloura-pink` : 'bg-veloura-muted',
        )}
      />
    </button>
  );
}
