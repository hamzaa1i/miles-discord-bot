'use client';

/** AI — proactive settings + explainers for chat, memory, vibe, fortune, recap. */

import { useParams } from 'next/navigation';
import { SettingsForm } from '@/components/SettingsForm';
import { MODULES } from '@/lib/modules';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';
import { SectionHeading } from '@/components/EmptyState';

const SUBFEATURES = [
  {
    id: 'chat',
    icon: '🌙',
    title: 'chat & memory',
    desc: 'mention aurelia or reply to her and she answers — remembering facts and recent conversation per member. members can /forget or opt out entirely with /privacy.',
  },
  {
    id: 'vibe',
    icon: '✧',
    title: 'vibe & fortune',
    desc: '/vibe reads the last four hours of a channel and describes the mood. /fortune draws one card a day — never the same twice. /pick, /askstars for the small decisions.',
  },
  {
    id: 'recap',
    icon: '📜',
    title: 'recap',
    desc: '/recap summarizes what a channel talked about while you were away — with an opt-out for anyone who prefers to stay out of the story.',
  },
];

export default function AiPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);

  return (
    <>
      <SettingsForm gid={gid} module={MODULES.ai}>
        <p className="mb-4 text-xs leading-relaxed text-veloura-muted/80">
          proactive chatter is the only guild-level ai switch — the rest of
          aurelia&apos;s mind is always available through commands.
        </p>
      </SettingsForm>

      <SectionHeading icon="🌙">the mind of aurelia</SectionHeading>
      <div className="grid gap-4 sm:grid-cols-3">
        {SUBFEATURES.map((f) => (
          <Card key={f.id} id={f.id} className="flex flex-col gap-2">
            <CardTitle icon={f.icon}>{f.title}</CardTitle>
            <p className="text-sm leading-relaxed text-veloura-muted">{f.desc}</p>
            <Badge tone="muted" className="mt-auto self-start">
              always on · per-user opt-out
            </Badge>
          </Card>
        ))}
      </div>
    </>
  );
}
