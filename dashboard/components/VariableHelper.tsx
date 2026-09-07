'use client';

/**
 * VariableHelper — collapsible list of aurelia template variables.
 * Click to insert at the cursor of the linked textarea.
 */

import { useRef, useState } from 'react';
import { cn } from '@/lib/format';

const GROUPS: { group: string; vars: { name: string; desc: string }[] }[] = [
  {
    group: 'member',
    vars: [
      { name: '{user}', desc: 'mention' },
      { name: '{user.name}', desc: 'username' },
      { name: '{user.id}', desc: 'user id' },
      { name: '{user.avatar}', desc: 'avatar url' },
    ],
  },
  {
    group: 'server',
    vars: [
      { name: '{server}', desc: 'server name' },
      { name: '{server.id}', desc: 'server id' },
      { name: '{server.icon}', desc: 'server icon url' },
      { name: '{membercount}', desc: 'member count' },
    ],
  },
  {
    group: 'extras',
    vars: [
      { name: '\\n', desc: 'line break' },
      { name: '---', desc: 'embed separator' },
      { name: '<#channelid>', desc: 'channel link' },
    ],
  },
];

export function VariableHelper({
  onInsert,
  compact,
}: {
  onInsert?: (text: string) => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const lastRef = useRef(onInsert);
  lastRef.current = onInsert;

  return (
    <div className={cn('rounded-[12px] border border-veloura-border/70 bg-veloura-navy/60', compact ? 'p-2' : 'p-3')}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex min-h-[36px] w-full items-center justify-between text-left text-xs text-veloura-muted transition hover:text-veloura-lavender"
      >
        <span>
          ✧ template variables <span className="text-veloura-muted/60">— {open ? 'hide' : 'show'}</span>
        </span>
        <span aria-hidden>{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          {GROUPS.map((g) => (
            <div key={g.group}>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-veloura-muted/70">
                {g.group}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {g.vars.map((v) => (
                  <button
                    key={v.name}
                    type="button"
                    title={`insert ${v.name} — ${v.desc}`}
                    disabled={!onInsert}
                    onClick={() => lastRef.current?.(v.name.replace('\\n', '\n'))}
                    className="rounded-full border border-veloura-border bg-veloura-card px-2.5 py-1 font-mono text-xs text-veloura-lavender transition hover:border-veloura-pink/50 hover:text-veloura-pink disabled:opacity-50"
                  >
                    {v.name}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-veloura-muted/60">
                {g.vars.map((v) => `${v.name} = ${v.desc}`).join(' · ')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
