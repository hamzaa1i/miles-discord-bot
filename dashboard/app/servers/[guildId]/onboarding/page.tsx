'use client';

/**
 * Onboarding — a soft first message with role buttons for new members.
 * Split out of the (former) roles tabs page into its own route.
 */

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { RoleMultiPicker } from '@/components/ChannelPicker';
import { LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { MessageEditor } from '@/components/MessageEditor';
import { useToast } from '@/components/ui/toast';
import type { Settings } from '@/lib/types';

const ONBOARDING_DEFAULTS: Settings = { enabled: false, welcome_text: '', roles: [] };

export default function OnboardingPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ob = useModuleSettings(gid, 'onboarding', ONBOARDING_DEFAULTS);

  if (ob.loading) {
    return <LoadingCard label={ob.verifying ? 'verifying permissions…' : 'loading onboarding…'} />;
  }
  if (ob.error && !ob.settings) return <ErrorCard message={ob.error} />;
  if (!ob.settings) return null;

  const o = (ob.settings ?? {}) as Record<string, Settings[keyof Settings]>;

  return (
    <>
      <ModuleCard
        icon="sparkles"
        title="onboarding"
        description="a soft first message with role buttons for new members"
      >
        <div className="mb-4 flex items-center justify-between gap-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 px-4 py-3">
          <div>
            <span className="text-sm text-veloura-text">onboarding enabled</span>
            <p className="mt-0.5 text-xs text-veloura-muted/70">
              when a member joins, aurelia dms them the welcome text + role buttons
            </p>
          </div>
          <input
            type="checkbox"
            className="h-5 w-5 accent-[#FFC0CB]"
            checked={Boolean(o.enabled)}
            onChange={(e) => ob.update({ enabled: e.target.checked })}
            aria-label="enable onboarding"
          />
        </div>

        <MessageEditor
          label="welcome text"
          help="{user} renders the new member's name · empty uses aurelia's built-in soft greeting"
          value={String(o.welcome_text ?? '')}
          onChange={(v) => ob.update({ welcome_text: v })}
          rows={4}
        />

        <div className="mt-4">
          <RoleMultiPicker
            label="selectable roles"
            help="roles new members can choose — roles above aurelia can't be granted and are hidden"
            value={Array.isArray(o.roles) ? (o.roles as string[]) : []}
            onChange={(v) => ob.update({ roles: v })}
          />
        </div>

        <p className="mt-5 text-xs leading-relaxed text-veloura-muted/70">
          need a join role without the buttons?{' '}
          <Link
            href={`/servers/${gid}/autorole`}
            className="text-veloura-lavender transition hover:text-veloura-pink"
          >
            autorole grants one silently on the autorole page →
          </Link>
        </p>
      </ModuleCard>

      <SaveBar
        dirty={ob.dirty}
        saving={ob.saving}
        error={ob.error}
        onSave={async () => {
          const ok = await ob.save();
          if (ok) toast.push('onboarding saved ✦', 'success');
        }}
        onRevert={ob.revert}
        onResetDefaults={async () => {
          const ok = await ob.resetDefaults();
          if (ok) toast.push('reset to defaults', 'info');
        }}
      />
    </>
  );
}
