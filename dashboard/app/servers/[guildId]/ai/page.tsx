'use client';

/** Chat & memory — proactive settings + how aurelia's mind works. */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { SettingsForm } from '@/components/SettingsForm';
import { MODULES } from '@/lib/modules';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';
import { SectionHeading } from '@/components/EmptyState';
import { Icon } from '@/components/icons';

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

      <SectionHeading icon="moon">the mind of aurelia</SectionHeading>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="flex flex-col gap-2">
          <CardTitle icon="moon">chat &amp; memory</CardTitle>
          <p className="text-sm leading-relaxed text-veloura-muted">
            mention aurelia or reply to her and she answers — remembering facts
            and recent conversation per member. members can /forget or opt out
            entirely with /privacy.
          </p>
          <Badge tone="muted" className="mt-auto self-start">
            always on · per-user opt-out
          </Badge>
        </Card>

        <Link href={`/servers/${gid}/vibe`} className="transition hover:scale-[1.02]">
          <Card className="flex h-full flex-col gap-2">
            <CardTitle icon="sparkles">vibe &amp; fortune</CardTitle>
            <p className="text-sm leading-relaxed text-veloura-muted">
              /vibe reads the last four hours of a channel and describes the
              mood. /fortune draws one card a day. /pick, /askstars for the
              small decisions.
            </p>
            <span className="mt-auto inline-flex items-center gap-1.5 text-xs text-veloura-lavender">
              guide on the vibe page
              <Icon name="chevronRight" size={13} />
            </span>
          </Card>
        </Link>

        <Link href={`/servers/${gid}/recap`} className="transition hover:scale-[1.02]">
          <Card className="flex h-full flex-col gap-2">
            <CardTitle icon="scroll">recap</CardTitle>
            <p className="text-sm leading-relaxed text-veloura-muted">
              /recap summarizes what a channel talked about while you were away
              — topics, participants, mood — with an opt-out for anyone who
              prefers to stay out of the story.
            </p>
            <span className="mt-auto inline-flex items-center gap-1.5 text-xs text-veloura-lavender">
              guide on the recap page
              <Icon name="chevronRight" size={13} />
            </span>
          </Card>
        </Link>
      </div>
    </>
  );
}
