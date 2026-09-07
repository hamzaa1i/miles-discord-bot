'use client';

/**
 * Polls — reaction polls with /poll.
 *
 * Command-driven: /poll create makes a poll, /poll end and /poll
 * results manage it. Nothing is configurable, but this page lists the
 * guild's CURRENTLY ACTIVE polls live from the bot's store so managers
 * can see what's running (and jump to the channel).
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints } from '@/lib/api';
import { useGuild } from '@/lib/guild';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { EmptyState } from '@/components/EmptyState';
import { Icon } from '@/components/icons';
import type { PollRow } from '@/lib/types';

function untilLabel(endTime: number | null): string {
  if (!endTime) return 'runs until ended manually';
  const diff = endTime * 1000 - Date.now();
  if (diff <= 0) return 'closing…';
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `ends in ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `ends in ${hours}h ${mins % 60}m`;
  return `ends in ${Math.floor(hours / 24)}d ${hours % 24}h`;
}

export default function PollsPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const { resources } = useGuild();
  const [polls, setPolls] = useState<PollRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    endpoints
      .polls(gid)
      .then((r) => {
        setPolls(r.polls ?? []);
        setError(null);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'could not load polls');
        setPolls([]);
      });
  }, [gid]);

  const channelName = (cid: string): string | null => {
    if (!cid || !resources) return null;
    const ch = resources.channels.find((c) => c.id === cid);
    return ch ? `#${ch.name}` : null;
  };

  return (
    <ModuleCard
      icon="barChart"
      title="polls"
      description="reaction polls with 🇦–🇩 — created in discord, visible here"
    >
      <Card>
        <CardTitle icon="barChart">make one</CardTitle>
        <code className="mt-3 block rounded-[10px] border border-veloura-border/50 bg-veloura-navy/60 px-3 py-2 text-xs text-veloura-lavender">
          /poll create question: movie night? option1: friday option2: saturday
          duration:2h
        </code>
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-veloura-muted">
          <span className="flex items-center gap-1.5">
            <Icon name="check" size={13} className="text-veloura-pink" />
            2–4 options, reactions 🇦 🇧 🇨 🇩 count the votes
          </span>
          <span className="flex items-center gap-1.5">
            <Icon name="timer" size={13} className="text-veloura-lavender" />
            optional duration (10m–7d) auto-ends the poll
          </span>
          <span className="flex items-center gap-1.5">
            <Icon name="scroll" size={13} className="text-veloura-lavender" />
            /poll results shows live counts · /poll end closes it
          </span>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-veloura-muted/70">
          ends show percentages and a bar graph; the creator or any mod can end
          early with <code className="text-veloura-lavender">/poll end [message id]</code>.
        </p>
      </Card>

      {error ? (
        <ErrorCard message={error} />
      ) : polls === null ? (
        <div className="mt-4">
          <LoadingCard label="gathering live polls…" />
        </div>
      ) : (
        <div className="mt-4">
          {polls.length === 0 ? (
            <EmptyState
              icon="barChart"
              title="no active polls"
              hint="create one in discord with /poll create — it appears here instantly"
            />
          ) : (
            <Card>
              <CardTitle icon="activity">active now</CardTitle>
              <ul className="mt-2 divide-y divide-veloura-border/40">
                {polls.map((p) => {
                  const chan = channelName(p.channel_id);
                  return (
                    <li key={p.message_id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                      <span className="min-w-0 flex-1 basis-52 truncate text-veloura-text">
                        {p.question}
                      </span>
                      <Badge tone="muted">{p.options.length} options</Badge>
                      {chan && (
                        <span className="text-xs text-veloura-lavender">{chan}</span>
                      )}
                      <span className="text-xs text-veloura-muted/70">{untilLabel(p.end_time)}</span>
                      <span className="text-xs text-veloura-muted/60">by {p.author_name || '—'}</span>
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}
        </div>
      )}

      <p className="mt-4 text-center text-xs text-veloura-muted/60">
        polls are command-driven — there&apos;s nothing to save on this page ✧
      </p>
    </ModuleCard>
  );
}
