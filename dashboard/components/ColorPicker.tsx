'use client';

/** ColorPicker — hex input + native color swatch + a few veloura presets. */

import { Field, TextInput } from './ui/primitives';
import { cn } from '@/lib/format';

const PRESETS = ['#FFC0CB', '#E6E6FA', '#A8E6CF', '#F4A8A8', '#FFD700', '#87CEEB', '#DDA0DD', '#F5F5F5'];

const HEX_RE = /^#?([0-9a-fA-F]{6})$/;

export function normalizeHex(raw: string): string | null {
  const m = HEX_RE.exec(raw.trim());
  return m ? `#${m[1].toLowerCase()}` : null;
}

export function ColorPicker({
  value,
  onChange,
  label = 'accent color',
  help,
}: {
  value: string | null;
  onChange: (v: string) => void;
  label?: string;
  help?: string;
}) {
  const hex = normalizeHex(value ?? '') ?? '#FFC0CB';

  return (
    <Field label={label} help={help ?? 'hex color like #FFC0CB'}>
      <div className="flex items-center gap-3">
        <label className="relative h-11 w-11 shrink-0 cursor-pointer overflow-hidden rounded-[12px] border border-veloura-border" aria-label="pick a color">
          <span className="absolute inset-0" style={{ background: hex }} />
          <input
            type="color"
            value={hex}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            className="absolute inset-0 cursor-pointer opacity-0"
          />
        </label>
        <TextInput
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#FFC0CB"
          className="w-36 font-mono"
          aria-label="hex color value"
        />
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              title={p}
              aria-label={`preset ${p}`}
              onClick={() => onChange(p)}
              className={cn(
                'h-6 w-6 rounded-full border border-veloura-border/60 transition hover:scale-110',
                hex.toLowerCase() === p.toLowerCase() && 'ring-2 ring-veloura-pink/60',
              )}
              style={{ background: p }}
            />
          ))}
        </div>
      </div>
    </Field>
  );
}
