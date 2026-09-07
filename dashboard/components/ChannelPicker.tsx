'use client';

/**
 * ChannelPicker / ChannelMultiPicker / RolePicker
 * Fed from GuildResources (fetched once per guild layout).
 */

import { useGuild } from '@/lib/guild';
import { channelTypeEmoji } from '@/lib/discord';
import { Select, Field } from './ui/primitives';
import { cn } from '@/lib/format';

export function ChannelPicker({
  value,
  onChange,
  label,
  help,
  allowNone = true,
  noneLabel = '— not set —',
  types,
  id,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  label?: string;
  help?: string;
  allowNone?: boolean;
  noneLabel?: string;
  /** channel types to include (default: text-ish channels) */
  types?: number[];
  id?: string;
}) {
  const { resources } = useGuild();
  const channels = (resources?.channels ?? []).filter(
    (c) => !types || types.includes(c.type),
  );
  const selected = channels.find((c) => c.id === value);

  return (
    <Field label={label} help={help ?? (selected ? undefined : help)} htmlFor={id}>
      <Select
        id={id}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
      >
        {allowNone && <option value="">{noneLabel}</option>}
        {channels.map((c) => (
          <option key={c.id} value={c.id}>
            {channelTypeEmoji(c.type)} {c.name}
          </option>
        ))}
      </Select>
      {selected && help && <p className="mt-1.5 text-xs text-veloura-muted/80">{help}</p>}
    </Field>
  );
}

export function ChannelMultiPicker({
  value,
  onChange,
  label,
  help,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  label?: string;
  help?: string;
}) {
  const { resources } = useGuild();
  const channels = (resources?.channels ?? []).filter((c) => c.type === 0 || c.type === 5);

  function toggle(id: string) {
    onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
  }

  return (
    <Field label={label} help={help}>
      <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto rounded-[12px] border border-veloura-border bg-veloura-navy p-3">
        {channels.length === 0 && (
          <span className="text-sm text-veloura-muted">no text channels</span>
        )}
        {channels.map((c) => {
          const on = value.includes(c.id);
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => toggle(c.id)}
              aria-pressed={on}
              className={cn(
                'min-h-[36px] rounded-full border px-3 py-1 text-sm transition',
                on
                  ? 'border-veloura-pink/60 bg-veloura-pink/15 text-veloura-pink'
                  : 'border-veloura-border text-veloura-muted hover:border-veloura-lavender/40 hover:text-veloura-text',
              )}
            >
              {channelTypeEmoji(c.type)} {c.name}
            </button>
          );
        })}
      </div>
      {value.length > 0 && (
        <p className="mt-1.5 text-xs text-veloura-muted/80">{value.length} selected</p>
      )}
    </Field>
  );
}

export function RolePicker({
  value,
  onChange,
  label,
  help,
  allowNone = true,
  id,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  label?: string;
  help?: string;
  allowNone?: boolean;
  id?: string;
}) {
  const { resources } = useGuild();
  const roles = resources?.roles ?? [];
  const selected = roles.find((r) => r.id === value);

  return (
    <Field label={label} help={help} htmlFor={id}>
      <Select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
        {allowNone && <option value="">— no role —</option>}
        {roles.map((r) => (
          <option key={r.id} value={r.id}>
            {r.color ? '●' : '○'} {r.name}
          </option>
        ))}
      </Select>
      {selected?.color && (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-veloura-muted/80">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: selected.color }}
          />
          role color {selected.color}
        </p>
      )}
    </Field>
  );
}
