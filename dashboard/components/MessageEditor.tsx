'use client';

/**
 * MessageEditor — textarea + VariableHelper + char counter.
 * Variable clicks insert at the cursor position.
 */

import { useRef, useState } from 'react';
import { VariableHelper } from './VariableHelper';
import { TextArea, Field } from './ui/primitives';
import { cn } from '@/lib/format';

export function MessageEditor({
  value,
  onChange,
  label,
  help,
  rows = 4,
  max = 2000,
  placeholder,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
  help?: string;
  rows?: number;
  max?: number;
  placeholder?: string;
  id?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function insert(text: string) {
    const el = ref.current;
    if (!el) {
      onChange(value + text);
      return;
    }
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const next = value.slice(0, start) + text + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      const pos = start + text.length;
      el.setSelectionRange(pos, pos);
    });
  }

  const len = value.length;

  return (
    <Field label={label} help={help} htmlFor={id}>
      <TextArea
        id={id}
        ref={ref}
        rows={rows}
        value={value}
        placeholder={placeholder}
        maxLength={max}
        onChange={(e) => onChange(e.target.value)}
        className="font-mono text-[13px] leading-relaxed"
      />
      <div className="mt-2 flex items-center justify-between gap-4">
        <span
          className={cn(
            'text-xs',
            len > max * 0.9 ? 'text-veloura-danger' : 'text-veloura-muted/70',
          )}
        >
          {len} / {max}
        </span>
      </div>
      <div className="mt-2">
        <VariableHelper onInsert={insert} compact />
      </div>
    </Field>
  );
}
