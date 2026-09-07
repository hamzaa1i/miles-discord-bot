/**
 * components/site/CommandGrid.tsx — PHASE M PART 1 §5.
 *
 * Interactive command showcase: a grid of popular commands with hover
 * micro-interactions, linking into the full 168-command reference at
 * /docs/commands. Pure CSS hover (no client js) + native tooltips.
 */

import Link from 'next/link';
import { cn } from '@/lib/format';
import { COMMAND_COUNT } from '@/lib/marketing';

interface Cmd {
  cmd: string;
  desc: string;
  cat: string;
}

const POPULAR: Cmd[] = [
  { cmd: '/aurelia', desc: 'talk to her naturally', cat: 'ai' },
  { cmd: '/daily', desc: 'claim your streak reward', cat: 'community' },
  { cmd: '/level', desc: 'your level card', cat: 'community' },
  { cmd: '/qotd', desc: 'the daily question setup', cat: 'community' },
  { cmd: '/poll', desc: 'reaction polls', cat: 'community' },
  { cmd: '/confess', desc: 'anonymous whispers', cat: 'community' },
  { cmd: '/mod warnings', desc: 'gentle case history', cat: 'moderation' },
  { cmd: '/giveaway', desc: 'gifts from the void', cat: 'community' },
  { cmd: '/ship', desc: 'compatibility % + poetic reason', cat: 'fun' },
  { cmd: '/recap', desc: 'what did i miss?', cat: 'ai' },
  { cmd: '/remind', desc: 'never forget again', cat: 'utility' },
  { cmd: '/privacy', desc: 'your data, your rules', cat: 'utility' },
];

const CAT_COLORS: Record<string, string> = {
  ai: 'text-veloura-lavender bg-veloura-lavender/10',
  community: 'text-veloura-pink bg-veloura-pink/10',
  moderation: 'text-veloura-danger bg-veloura-danger/10',
  fun: 'text-veloura-pink bg-veloura-pink/10',
  utility: 'text-veloura-success bg-veloura-success/10',
};

export function CommandGrid() {
  return (
    <section aria-label="commands preview" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-6">
        <header className="mb-10 text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">
            a taste of the spellbook
          </p>
          <h2 className="font-heading mt-2 text-3xl text-veloura-text sm:text-4xl">
            {COMMAND_COUNT} commands, zero archaeology
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-veloura-muted">
            slash commands, natural @aurelia language and custom prefixes —
            three ways to say the same thing, whichever feels softest.
          </p>
        </header>

        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {POPULAR.map((c) => (
            <li key={c.cmd}>
              <Link
                href="/docs/commands"
                className="group veloura-card flex items-start gap-3 p-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-veloura-pink/40 hover:shadow-glow"
                aria-label={`${c.cmd} — ${c.desc}. see all commands in the documentation`}
              >
                <code className="group-hover:text-veloura-pink rounded-[8px] bg-veloura-navy px-2 py-1 font-mono text-xs text-veloura-text transition-colors">
                  {c.cmd}
                </code>
                <span className="min-w-0 flex-1 text-xs leading-relaxed text-veloura-muted">
                  {c.desc}
                </span>
                <span
                  className={cn(
                    'shrink-0 rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider opacity-80',
                    CAT_COLORS[c.cat] ?? 'bg-veloura-card-hover text-veloura-muted',
                  )}
                >
                  {c.cat}
                </span>
              </Link>
            </li>
          ))}
        </ul>

        <p className="mt-8 text-center">
          <Link
            href="/docs/commands"
            className="veloura-button-ghost group px-5 text-sm"
          >
            explore all {COMMAND_COUNT} commands
            <span className="transition-transform duration-300 group-hover:translate-x-1" aria-hidden>
              →
            </span>
          </Link>
        </p>
      </div>
    </section>
  );
}
