'use client';

/**
 * Vibe & fortune — command guide for the mood-reading suite.
 *
 * These are per-channel / per-user bot commands (nothing to configure
 * at the guild level) — the page explains each one, shows usage
 * examples, and points at the per-user privacy opt-outs.
 */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';

const COMMANDS = [
  {
    icon: 'sparkles',
    title: '/vibe',
    body: 'reads the last 4 hours of the current channel and describes the mood in aurelia\'s voice — topics, energy, the shape of the conversation.',
    usage: '/vibe',
    notes: ['5-minute cooldown per channel', 'members opted out via /privacy are skipped'],
    tag: 'per-channel · no config',
  },
  {
    icon: 'moon',
    title: '/fortune',
    body: 'one fortune card per person per day — a short, soft, hopeful line drawn fresh each morning, never the same twice.',
    usage: '/fortune',
    notes: ['10s cooldown, one draw per day', 'yesterday\'s card shows again until midnight utc'],
    tag: 'per-user',
  },
  {
    icon: 'check',
    title: '/pick',
    body: 'hand aurelia the options and she chooses — "tea or coffee", "left or right". deterministic for the same question in the same minute.',
    usage: '/pick options: tea, coffee, matcha',
    notes: ['comma-separated options', '2–10 options work best'],
    tag: 'per-user',
  },
  {
    icon: 'star',
    title: '/askstars',
    body: 'ask the stars a yes/no question and get a reading — with a mood, not just an answer.',
    usage: '/askstars question: should i stream tonight?',
    notes: ['ephemeral reply — only you see it'],
    tag: 'per-user',
  },
];

export default function VibePage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);

  return (
    <ModuleCard
      icon="sparkles"
      title="vibe & fortune"
      description="mood readings, daily cards and small decisions — all command-driven, zero config"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {COMMANDS.map((c) => (
          <Card key={c.title} className="flex flex-col gap-2">
            <CardTitle icon={c.icon}>{c.title}</CardTitle>
            <p className="text-sm leading-relaxed text-veloura-muted">{c.body}</p>
            <code className="block rounded-[10px] border border-veloura-border/50 bg-veloura-navy/60 px-3 py-2 text-xs text-veloura-lavender">
              {c.usage}
            </code>
            <ul className="space-y-1">
              {c.notes.map((n) => (
                <li key={n} className="text-xs text-veloura-muted/70">
                  ✧ {n}
                </li>
              ))}
            </ul>
            <Badge tone="muted" className="mt-auto self-start">
              {c.tag}
            </Badge>
          </Card>
        ))}
      </div>

      <p className="mt-5 text-xs leading-relaxed text-veloura-muted/70">
        members can opt out of appearing in vibe readings with{' '}
        <code className="text-veloura-lavender">/privacy</code> — their messages are
        skipped entirely. the proactive-chatter switch that lets aurelia drift into
        conversation lives on{' '}
        <Link
          href={`/servers/${gid}/ai`}
          className="text-veloura-lavender transition hover:text-veloura-pink"
        >
          the chat &amp; memory page →
        </Link>
      </p>
    </ModuleCard>
  );
}
