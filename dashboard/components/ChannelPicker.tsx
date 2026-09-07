'use client';

/**
 * ChannelPicker / ChannelMultiPicker / RolePicker / RoleMultiPicker
 * Fed from GuildResources (fetched once per guild layout, 5-min cached).
 *
 * Live-testing hardening:
 *  - loading state: skeleton options while channels load (never a
 *    silent empty list),
 *  - error state: a retry row when the fetch failed — "no channels"
 *    only shows when the list genuinely loaded empty,
 *  - channels default to text-like types the BOT can post in
 *    (bot_can_send, computed server-side from Discord),
 *  - RoleMultiPicker replaces the old (wrong) channel-based
 *    multi-picker used for onboarding selectable roles.
 */

import { useGuild } from '@/lib/guild';
import { channelTypeEmoji } from '@/lib/discord';
import { roleColorHex } from '@/lib/types';
import { Icon } from '@/components/icons';
import { Select, Field, Skeleton } from './ui/primitives';
import { cn } from '@/lib/format';

/** text-like channel types: text, announcement, forum (15), media (16) */
const TEXT_TYPES = [0, 5, 15, 16];

function PickerNotice({
  state,
  onRetry,
}: {
  state: 'loading' | 'error' | 'empty';
  onRetry?: () => void;
}) {
  if (state === 'loading') {
    return (
      <div className="space-y-2 py-1" aria-live="polite">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-4/5" />
      </div>
    );
  }
  if (state === 'error') {
    return (
      <div className="flex items-center justify-between gap-3 rounded-[12px] border border-veloura-danger/30 bg-veloura-danger/5 px-3.5 py-2.5 text-sm">
        <span className="text-veloura-danger">couldn&apos;t load the list</span>
        <button
          type="button"
          onClick={onRetry}
          className="flex min-h-[36px] items-center gap-1.5 text-xs text-veloura-lavender transition hover:text-veloura-pink"
        >
          <Icon name="refresh" size={13} />
          retry
        </button>
      </div>
    );
  }
  return <p className="py-1 text-sm text-veloura-muted">nothing here yet</p>;
}

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
  /** channel types to include (default: text-ish channels the bot can post in) */
  types?: number[];
  id?: string;
}) {
  const { resources, resourcesLoading, resourcesError, reloadResources } = useGuild();
  const channels = (resources?.channels ?? [])
    .filter((c) => (types ? types.includes(c.type) : TEXT_TYPES.includes(c.type)))
    .filter((c) => c.bot_can_send !== false);
  const selected = channels.find((c) => c.id === value);
  const state: 'loading' | 'error' | 'empty' | 'ok' = resourcesError
    ? 'error'
    : resourcesLoading && !resources
      ? 'loading'
      : channels.length === 0
        ? 'empty'
        : 'ok';

  return (
    <Field label={label} help={help} htmlFor={id}>
      {state === 'ok' ? (
        <Select
          id={id}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value || null)}
        >
          {allowNone && <option value="">{noneLabel}</option>}
          {channels.map((c) => (
            <option key={c.id} value={c.id}>
              {channelTypeEmoji(c.type)} {c.parent_name ? `${c.parent_name} / ` : ''}
              {c.name}
            </option>
          ))}
        </Select>
      ) : state === 'error' ? (
        <PickerNotice state="error" onRetry={() => void reloadResources()} />
      ) : state === 'loading' ? (
        <PickerNotice state="loading" />
      ) : (
        <PickerNotice state="empty" />
      )}
      {state === 'ok' && selected && help && (
        <p className="mt-1.5 text-xs text-veloura-muted/80">{help}</p>
      )}
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
  const { resources, resourcesLoading, resourcesError, reloadResources } = useGuild();
  const channels = (resources?.channels ?? [])
    .filter((c) => c.type === 0 || c.type === 5)
    .filter((c) => c.bot_can_send !== false);

  function toggle(id: string) {
    onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
  }

  return (
    <Field label={label} help={help}>
      <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto rounded-[12px] border border-veloura-border bg-veloura-navy p-3">
        {resourcesError && (
          <div className="flex w-full items-center justify-between gap-3 text-sm">
            <span className="text-veloura-danger">couldn&apos;t load channels</span>
            <button
              type="button"
              onClick={() => void reloadResources()}
              className="flex min-h-[36px] items-center gap-1.5 text-xs text-veloura-lavender transition hover:text-veloura-pink"
            >
              <Icon name="refresh" size={13} />
              retry
            </button>
          </div>
        )}
        {!resourcesError && resourcesLoading && !resources && (
          <div className="flex w-full flex-wrap gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-24 rounded-full" />
            ))}
          </div>
        )}
        {!resourcesError && !resourcesLoading && channels.length === 0 && (
          <span className="text-sm text-veloura-muted">no text channels yet</span>
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
                'min-h-[40px] rounded-full border px-3 py-1 text-sm transition',
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
  const { resources, resourcesLoading, resourcesError, reloadResources } = useGuild();
  const roles = resources?.roles ?? [];
  const selected = roles.find((r) => r.id === value);
  const selectedColor = selected ? roleColorHex(selected.color) : null;
  const state: 'loading' | 'error' | 'empty' | 'ok' = resourcesError
    ? 'error'
    : resourcesLoading && !resources
      ? 'loading'
      : roles.length === 0
        ? 'empty'
        : 'ok';

  return (
    <Field label={label} help={help} htmlFor={id}>
      {state === 'ok' ? (
        <Select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
          {allowNone && <option value="">— no role —</option>}
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.color ? '●' : '○'} {r.name}
            </option>
          ))}
        </Select>
      ) : state === 'error' ? (
        <PickerNotice state="error" onRetry={() => void reloadResources()} />
      ) : state === 'loading' ? (
        <PickerNotice state="loading" />
      ) : (
        <PickerNotice state="empty" />
      )}
      {selectedColor && (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-veloura-muted/80">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: selectedColor }}
          />
          role color {selectedColor}
        </p>
      )}
    </Field>
  );
}

/** Multi-select roles (onboarding selectable roles, etc.). */
export function RoleMultiPicker({
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
  const { resources, resourcesLoading, resourcesError, reloadResources } = useGuild();
  const roles = resources?.roles ?? [];

  function toggle(id: string) {
    onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
  }

  return (
    <Field label={label} help={help}>
      <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto rounded-[12px] border border-veloura-border bg-veloura-navy p-3">
        {resourcesError && (
          <div className="flex w-full items-center justify-between gap-3 text-sm">
            <span className="text-veloura-danger">couldn&apos;t load roles</span>
            <button
              type="button"
              onClick={() => void reloadResources()}
              className="flex min-h-[36px] items-center gap-1.5 text-xs text-veloura-lavender transition hover:text-veloura-pink"
            >
              <Icon name="refresh" size={13} />
              retry
            </button>
          </div>
        )}
        {!resourcesError && resourcesLoading && !resources && (
          <div className="flex w-full flex-wrap gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-24 rounded-full" />
            ))}
          </div>
        )}
        {!resourcesError && !resourcesLoading && roles.length === 0 && (
          <span className="text-sm text-veloura-muted">
            no assignable roles yet — roles above aurelia or bot-managed
            roles are hidden
          </span>
        )}
        {roles.map((r) => {
          const on = value.includes(r.id);
          const hex = roleColorHex(r.color);
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => toggle(r.id)}
              aria-pressed={on}
              className={cn(
                'flex min-h-[40px] items-center gap-2 rounded-full border px-3 py-1 text-sm transition',
                on
                  ? 'border-veloura-pink/60 bg-veloura-pink/15 text-veloura-pink'
                  : 'border-veloura-border text-veloura-muted hover:border-veloura-lavender/40 hover:text-veloura-text',
              )}
            >
              {hex && (
                <span
                  aria-hidden
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ background: hex }}
                />
              )}
              {r.name}
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
