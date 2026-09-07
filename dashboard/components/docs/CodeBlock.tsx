'use client';

/**
 * components/docs/CodeBlock.tsx — docs code blocks.
 *
 * Dark code surface with a copy-to-clipboard button (PHASE M PART 2
 * requirement) and a tiny regex highlighter for shell/discord-command
 * snippets: the command word gets the pink accent, flags/keys the
 * lavender accent. Deliberately not a full syntax highlighter —
 * the docs only contain commands, paths and small config snippets.
 */

import { useState } from 'react';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';

export function CodeBlock({
  children,
  title,
  className,
}: {
  children: string;
  title?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — ignore */
    }
  }

  const lines = children.replace(/\n$/, '').split('\n');

  return (
    <div className={cn('no-print group relative my-4 overflow-hidden rounded-card border border-veloura-border bg-veloura-navy-deep', className)}>
      <div className="flex items-center justify-between border-b border-veloura-border/60 px-4 py-2">
        <span className="font-mono text-[11px] uppercase tracking-wider text-veloura-muted/70">
          {title ?? 'shell'}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? 'copied to clipboard' : 'copy code to clipboard'}
          className="flex items-center gap-1 rounded-[8px] px-2 py-1 text-[11px] text-veloura-muted opacity-70 transition hover:bg-veloura-card-hover hover:text-veloura-text hover:opacity-100 focus:opacity-100"
        >
          <Icon name={copied ? 'check' : 'pencil'} size={12} />
          {copied ? 'copied ✦' : 'copy'}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3.5 text-[13px] leading-relaxed">
        <code className="font-mono">
          {lines.map((line, i) => (
            <span key={i} className="block whitespace-pre">
              <HighlightLine line={line} />
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}

/** highlight: leading /command or word → pink; <required>/[optional]/@mention → lavender. */
function HighlightLine({ line }: { line: string }) {
  const cmdMatch = line.match(/^(\s*)(\/[\w-]+|[\w./-]+(?:\s+\w+)*?)(\s|$)/);
  if (!cmdMatch) return <span className="text-veloura-muted">{line}</span>;

  const [, indent, cmd, tail = ''] = cmdMatch;
  const rest = line.slice(indent.length + cmd.length);

  return (
    <>
      <span className="text-veloura-pink">{cmd}</span>
      <span className="text-veloura-lavender/40">{tail}</span>
      <HighlightRest text={rest} />
    </>
  );
}

function HighlightRest({ text }: { text: string }) {
  // highlight <required> and [optional] placeholders + @mentions
  const parts = text.split(/(<[^>]+>|\[@[^\]]+\]|@[\w-]+)/g);
  return (
    <>
      {parts.map((p, i) => {
        if (/^<[^>]+>$/.test(p) || /^\[@[^\]]+\]$/.test(p) || /^@[\w-]+$/.test(p)) {
          return (
            <span key={i} className="text-veloura-lavender">
              {p}
            </span>
          );
        }
        return <span key={i} className="text-veloura-muted">{p}</span>;
      })}
    </>
  );
}
