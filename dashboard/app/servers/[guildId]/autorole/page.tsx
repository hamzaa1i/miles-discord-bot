'use client';

/**
 * Autorole — the single role granted the moment a member joins.
 * Split out of the (former) roles tabs page into its own route.
 */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { RolePicker } from '@/components/ChannelPicker';
import { LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import type { Settings } from '@/lib/types';

const AUTOROLE_DEFAULTS: Settings = { role_id: null };

export default function AutorolePage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ar = useModuleSettings(gid, 'autorole', AUTOROLE_DEFAULTS);

  if (ar.loading) {
    return <LoadingCard label={ar.verifying ? 'verifying permissions…' : 'loading autorole…'} />;
  }
  if (ar.error && !ar.settings) return <ErrorCard message={ar.error} />;
  if (!ar.settings) return null;

  const a = (ar.settings ?? {}) as Record<string, Settings[keyof Settings]>;

  return (
    <>
      <ModuleCard
        icon="sparkles"
        title="autorole"
        description="granted automatically the moment a member joins"
      >
        <RolePicker
          id="autorole-role"
          label="join role"
          help="aurelia hands this out as each member arrives — pick one below her own top role"
          value={(a.role_id as string | null) ?? null}
          onChange={(v) => ar.update({ role_id: v })}
        />

        <p className="mt-5 text-xs leading-relaxed text-veloura-muted/70">
          prefer letting members choose from several roles?{' '}
          <Link
            href={`/servers/${gid}/self-roles`}
            className="text-veloura-lavender transition hover:text-veloura-pink"
          >
            self-roles panels are managed in discord →
          </Link>{' '}
          ·{' '}
          <Link
            href={`/servers/${gid}/onboarding`}
            className="text-veloura-lavender transition hover:text-veloura-pink"
          >
            onboarding adds role buttons for new members →
          </Link>
        </p>
      </ModuleCard>

      <SaveBar
        dirty={ar.dirty}
        saving={ar.saving}
        error={ar.error}
        onSave={async () => {
          const ok = await ar.save();
          if (ok) toast.push('autorole saved ✦', 'success');
        }}
        onRevert={ar.revert}
      />
    </>
  );
}
