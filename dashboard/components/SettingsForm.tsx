'use client';

/**
 * SettingsForm — schema-driven settings editor.
 * Renders FieldDef lists (lib/modules.ts) with the right pickers,
 * grouped by optional `section` headings, with a SaveBar.
 */

import { useMemo } from 'react';
import type { FieldDef, ModuleDef } from '@/lib/modules';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { useToast } from '@/components/ui/toast';
import { ChannelPicker, ChannelMultiPicker } from './ChannelPicker';
import { RolePicker } from './ChannelPicker';
import { ColorPicker } from './ColorPicker';
import { MessageEditor } from './MessageEditor';
import { ToggleSwitch } from './ToggleSwitch';
import { SaveBar } from './SaveBar';
import { ModuleCard } from './ModuleCard';
import { TextInput, Select, Card, LoadingCard, ErrorCard } from './ui/primitives';
import type { Settings } from '@/lib/types';

function renderField(
  field: FieldDef,
  value: unknown,
  onChange: (v: unknown) => void,
): React.ReactNode {
  const id = `field-${field.key}`;
  switch (field.type) {
    case 'boolean':
      return (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 px-4 py-3">
          <label htmlFor={id} className="text-sm text-veloura-text">
            {field.label}
          </label>
          <ToggleSwitch
            checked={Boolean(value)}
            onChange={onChange}
            label={field.label}
          />
        </div>
      );
    case 'channel':
      return (
        <ChannelPicker
          id={id}
          label={field.label}
          help={field.help}
          value={(value as string | null) ?? null}
          onChange={onChange}
        />
      );
    case 'channelMulti':
      return (
        <ChannelMultiPicker
          label={field.label}
          help={field.help}
          value={Array.isArray(value) ? (value as string[]) : []}
          onChange={onChange}
        />
      );
    case 'role':
      return (
        <RolePicker
          id={id}
          label={field.label}
          help={field.help}
          value={(value as string | null) ?? null}
          onChange={onChange}
        />
      );
    case 'color':
      return (
        <ColorPicker
          label={field.label}
          help={field.help}
          value={(value as string | null) ?? ''}
          onChange={onChange as (v: string) => void}
        />
      );
    case 'textarea':
      return (
        <MessageEditor
          id={id}
          label={field.label}
          help={field.help}
          rows={field.rows ?? 5}
          value={typeof value === 'string' ? value : ''}
          onChange={onChange as (v: string) => void}
        />
      );
    case 'number':
      return (
        <div className="mb-4">
          <label htmlFor={id} className="veloura-label">
            {field.label}
          </label>
          <TextInput
            id={id}
            type="number"
            min={field.min}
            max={field.max}
            step={field.step}
            placeholder={field.placeholder}
            value={value === null || value === undefined ? '' : String(value)}
            onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
          />
          {field.help && <p className="mt-1.5 text-xs text-veloura-muted/80">{field.help}</p>}
        </div>
      );
    case 'select':
      return (
        <div className="mb-4">
          <label htmlFor={id} className="veloura-label">
            {field.label}
          </label>
          <Select id={id} value={String(value ?? '')} onChange={(e) => onChange(e.target.value)}>
            {(field.options ?? []).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </div>
      );
    default:
      return (
        <div className="mb-4">
          <label htmlFor={id} className="veloura-label">
            {field.label}
          </label>
          <TextInput
            id={id}
            placeholder={field.placeholder}
            value={value === null || value === undefined ? '' : String(value)}
            onChange={(e) => onChange(e.target.value)}
          />
          {field.help && <p className="mt-1.5 text-xs text-veloura-muted/80">{field.help}</p>}
        </div>
      );
  }
}

export function SettingsForm({
  gid,
  module,
  children,
  extraContent,
}: {
  gid: string;
  /** lib/modules.ts entry */
  module: ModuleDef;
  /** content rendered above the form (rich pages) */
  children?: React.ReactNode;
  /** content rendered below the form */
  extraContent?: React.ReactNode;
}) {
  const toast = useToast();
  const ms = useModuleSettings(gid, module.settings ?? module.slug, module.defaults);

  const grouped = useMemo(() => {
    const sections = new Map<string, FieldDef[]>();
    for (const f of module.fields) {
      const key = f.section ?? '';
      if (!sections.has(key)) sections.set(key, []);
      sections.get(key)!.push(f);
    }
    return [...sections.entries()];
  }, [module.fields]);

  if (ms.loading) return <LoadingCard label={`loading ${module.title}…`} />;
  if (ms.error && !ms.settings)
    return (
      <ErrorCard
        message={ms.error}
        action={
          <button className="veloura-button-ghost" onClick={() => window.location.reload()}>
            retry
          </button>
        }
      />
    );
  if (!ms.settings) return null;

  const enabledField = module.fields.find((f) => f.key === 'enabled');

  return (
    <>
      <ModuleCard
        icon={module.icon}
        title={module.title}
        description={module.short}
        enabled={enabledField ? Boolean(ms.settings.enabled) : undefined}
        onToggle={
          enabledField
            ? async (next) => {
                ms.update({ enabled: next });
                const ok = await ms.patch({ enabled: next });
                if (ok) toast.push(`${module.title} ${next ? 'enabled' : 'disabled'} ✦`, 'success');
              }
            : undefined
        }
      >
        {children}
        {grouped.map(([section, fields]) => (
          <Card key={section || 'main'} className={section ? 'mt-4' : ''}>
            {section && (
              <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.2em] text-veloura-lavender/70">
                {section}
              </p>
            )}
            {fields.map((f) => (
              <div key={f.key}>
                {renderField(f, ms.settings?.[f.key], (v) => ms.update({ [f.key]: v }))}
              </div>
            ))}
          </Card>
        ))}
        {extraContent}
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('saved ✦', 'success');
        }}
        onRevert={ms.revert}
        onResetDefaults={
          module.defaults
            ? async () => {
                const ok = await ms.resetDefaults();
                if (ok) toast.push('reset to defaults', 'info');
              }
            : undefined
        }
      />
    </>
  );
}

/** Helper to build a thin module page from just the ModuleDef. */
export function ModulePage({ gid, module }: { gid: string; module: ModuleDef }) {
  return <SettingsForm gid={gid} module={module} />;
}
