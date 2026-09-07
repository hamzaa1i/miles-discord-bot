'use client';

/**
 * Recap — the /recap channel digest guide.
 *
 * /recap is a per-user command that summarizes what a channel talked
 * about while the caller was away. Nothing is configurable at the
 * guild level — this page explains usage, limits and the opt-out.
 */

import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';

export default function RecapPage() {
  return (
    <ModuleCard
      icon="scroll"
      title="recap"
      description="&quot;what did i miss?&quot; — a digest of the channel's last hours"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="flex flex-col gap-2">
          <CardTitle icon="scroll">how it works</CardTitle>
          <p className="text-sm leading-relaxed text-veloura-muted">
            /recap fetches the channel&apos;s recent messages, sends the transcript to
            aurelia&apos;s big reasoning model, and returns an aesthetic digest: topics
            discussed, who was active, and the overall vibe of the chat.
          </p>
          <code className="block rounded-[10px] border border-veloura-border/50 bg-veloura-navy/60 px-3 py-2 text-xs text-veloura-lavender">
            /recap
          </code>
          <p className="text-xs text-veloura-muted/70">
            recap of the current channel, last 2 hours
          </p>
          <code className="block rounded-[10px] border border-veloura-border/50 bg-veloura-navy/60 px-3 py-2 text-xs text-veloura-lavender">
            /recap channel:#general hours:6
          </code>
          <p className="text-xs text-veloura-muted/70">
            last 6 hours of #general — you must be able to read the channel
          </p>
        </Card>

        <Card className="flex flex-col gap-2">
          <CardTitle icon="shield">guards &amp; limits</CardTitle>
          <ul className="space-y-2 text-sm leading-relaxed text-veloura-muted">
            <li>✧ 60-second cooldown per person (protects the model quota)</li>
            <li>✧ the caller must have read access to the target channel</li>
            <li>✧ bots and slash-command output are excluded from transcripts</li>
            <li>✧ fewer than 3 qualifying messages → &ldquo;not enough activity to summarize&rdquo;</li>
          </ul>
          <Badge tone="muted" className="mt-auto self-start">
            per-user · no config
          </Badge>
        </Card>
      </div>

      <p className="mt-5 text-xs leading-relaxed text-veloura-muted/70">
        anyone who prefers to stay out of the story can opt out with{' '}
        <code className="text-veloura-lavender">/privacy</code> — their messages are
        skipped in every recap, vibe reading and memory extraction at once.
      </p>
    </ModuleCard>
  );
}
