'use client';

/** Fun & polls — usage guide for the delightfully useless. */

import { useParams } from 'next/navigation';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';

const THINGS = [
  {
    icon: '📊',
    title: 'polls',
    body: '/poll question + options — reactions 🇦..🇩 count the votes. ends with /poll end, by its creator or a mod.',
    tag: 'no config needed',
  },
  {
    icon: '🫂',
    title: 'ship',
    body: '/ship match @someone — a deterministic score (same pair, same day, same answer), poetic reasoning, history kept.',
    tag: 'opt-out with /ship optout',
  },
  {
    icon: '💌',
    title: 'confessions',
    body: '/confess whisper — anonymous posts counted per channel. configure the channel on the confessions page.',
    tag: 'see confessions page',
  },
  {
    icon: '⏰',
    title: 'reminders',
    body: '/remind create 2h water the plants — recurring daily/weekly/monthly, listed with /remind list.',
    tag: 'per-user',
  },
  {
    icon: '🎁',
    title: 'daily & fortune',
    body: '/daily claims streak xp with milestone bonuses. /fortune draws the day\u2019s card — never twice the same.',
    tag: 'per-user',
  },
  {
    icon: '🎬',
    title: 'time capsules',
    body: '/capsule create 6m message — sealed until the unlock date, delivered publicly or by dm.',
    tag: 'id: #reminders',
  },
];

export default function FunPage() {
  const params = useParams<{ guildId: string }>();
  void params;

  return (
    <ModuleCard
      icon="✧"
      title="fun & polls"
      description="the delightfully useful corners — all command-driven, zero config"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {THINGS.map((t) => (
          <Card key={t.title} className="flex flex-col gap-2" id={t.tag.startsWith('id:') ? t.tag.slice(3) : undefined}>
            <CardTitle icon={t.icon}>{t.title}</CardTitle>
            <p className="text-sm leading-relaxed text-veloura-muted">{t.body}</p>
            <Badge tone="muted" className="mt-auto self-start">
              {t.tag.startsWith('id:') ? t.tag.slice(4) : t.tag}
            </Badge>
          </Card>
        ))}
      </div>
    </ModuleCard>
  );
}
