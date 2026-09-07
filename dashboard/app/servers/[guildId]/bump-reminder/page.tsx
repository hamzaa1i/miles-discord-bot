'use client';

import { useParams } from 'next/navigation';
import { SettingsForm } from '@/components/SettingsForm';
import { MODULES } from '@/lib/modules';

export default function Page() {
  const params = useParams<{ guildId: string }>();
  return <SettingsForm gid={String(params.guildId)} module={MODULES.bumpReminder} />;
}
