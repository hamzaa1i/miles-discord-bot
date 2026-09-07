/**
 * components/docs/Markdown.tsx — tiny inline markdown renderer for docs
 * prose (subset: **bold**, *italic*, `code`, [links](url)). Keeps the
 * generated docs data renderable without pulling in a full markdown
 * engine — the docs never contain tables or nested lists.
 */

import type { ReactNode } from 'react';

/** Split a string into styled React nodes. */
export function Markdown({ text, className }: { text: string; className?: string }) {
  return <p className={className}>{renderInline(text)}</p>;
}

export function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // token order matters: code first (so ** inside `..` stays literal-ish)
  const pattern = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;

  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('`')) {
      nodes.push(
        <code key={key++} className="rounded-[6px] bg-veloura-card-hover px-1.5 py-0.5 font-mono text-[0.85em] text-veloura-lavender">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith('**')) {
      nodes.push(
        <strong key={key++} className="font-medium text-veloura-text">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else if (tok.startsWith('*') && tok.length > 2) {
      nodes.push(
        <em key={key++} className="text-veloura-muted">
          {tok.slice(1, -1)}
        </em>,
      );
    } else if (tok.startsWith('[')) {
      const lm = tok.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (lm) {
        const [, label, href] = lm;
        const external = href.startsWith('http');
        nodes.push(
          external ? (
            <a key={key++} href={href} target="_blank" rel="noopener noreferrer"
               className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
              {label}
            </a>
          ) : (
            <a key={key++} href={href}
               className="text-veloura-pink underline decoration-veloura-pink/40 underline-offset-2">
              {label}
            </a>
          ),
        );
      }
    }
    last = m.index + tok.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}
