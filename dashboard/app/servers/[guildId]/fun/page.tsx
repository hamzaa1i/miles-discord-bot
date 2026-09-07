'use client';

/** Fun & games — usage guide for the delightfully useless. */

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';
import { Icon } from '@/components/icons';

const THINGS = [
  {
    icon: 'barChart',
    title: 'polls',
    body: '/poll question + options — reactions 🇦..🇩 count the votes. ends with /poll end, by its creator or a mod.',
    tag: 'command-driven · no config',
    link: 'polls',
    linkLabel: 'see live polls →',
  },
  {
    icon: 'heart',
    title: 'ship',
    body: '/ship match @someone — a deterministic score (same pair, same day, same answer), poetic reasoning, history kept.',
    tag: 'opt-out with /ship optout',
  },
  {
    icon: 'messageSquare',
    title: 'confessions',
    body: '/confess whisper — anonymous posts counted per channel. configure the channel on the confessions page.',
    tag: 'see confessions page',
  },
  {
    icon: 'timer',
    title: 'reminders',
    body: '/remind create 2h water the plants — recurring daily/weekly/monthly. view and cancel yours on the reminders page.',
    tag: 'per-user · see reminders page',
    link: 'reminders',
    linkLabel: 'manage your reminders →',
  },
  {
    icon: 'moon',
    title: 'daily & fortune',
    body: '/daily claims streak xp with milestone bonuses. /fortune draws the day\u2019s card — never twice the same.',
    tag: 'per-user',
    link: 'vibe',
    linkLabel: 'guide on the vibe page →',
  },
  {
    icon: 'scroll',
    title: 'time capsules',
    body: '/capsule create 6m message — sealed until the unlock date, delivered publicly or by dm.',
    tag: 'per-user',
  },
];

export default function FunPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);

  return (
    <ModuleCard
      icon="sparkles"
      title="fun & games"
      description="the delightfully useful corners — all command-driven, zero config"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {THINGS.map((t) => (
          <Card key={t.title} className="flex flex-col gap-2">
            <CardTitle icon={t.icon}>{t.title}</CardTitle>
            <p className="text-sm leading-relaxed text-veloura-muted">{t.body}</p>
            {t.link ? (
              <Link
                href={`/servers/${gid}/${t.link}`}
                className="mt-auto inline-flex items-center gap-1.5 self-start text-xs text-veloura-lavender transition hover:text-veloura-pink"
              >
                {t.linkLabel}
                <Icon name="chevronRight" size={13} />
              </Link>
            ) : (
              <Badge tone="muted" className="mt-auto self-start">
                {t.tag}
              </Badge>
            )}
          </Card>
        ))}
      </div>
    </ModuleCard>
  );
}
