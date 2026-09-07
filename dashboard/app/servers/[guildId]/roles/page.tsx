'use client';

/** Roles — tabs: autorole, self-roles, color roles, onboarding (level rewards → leveling page). */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { useHashTab } from '@/lib/useHashTab';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { RolePicker, RoleMultiPicker } from '@/components/ChannelPicker';
import { Card, CardTitle, Badge, Tabs, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { EmptyState, SectionHeading } from '@/components/EmptyState';
import { MessageEditor } from '@/components/MessageEditor';
import { useToast } from '@/components/ui/toast';
import { timeAgo } from '@/lib/format';
import type { ColorRoleRow, Settings } from '@/lib/types';

const AUTOROLE_DEFAULTS: Settings = { role_id: null };
const ONBOARDING_DEFAULTS: Settings = { enabled: false, welcome_text: '', roles: [] };

export default function RolesPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  // tabs sync to the url fragment: roles#onboarding opens onboarding
  const [tab, setTab] = useHashTab(
    ['autorole', 'selfroles', 'colors', 'onboarding'],
    'autorole',
  );

  const autorole = useModuleSettings(gid, 'autorole', AUTOROLE_DEFAULTS);
  const onboarding = useModuleSettings(gid, 'onboarding', ONBOARDING_DEFAULTS);
  const [colorRoles, setColorRoles] = useState<ColorRoleRow[] | null>(null);

  useEffect(() => {
    if (tab !== 'colors') return;
    endpoints
      .colorRoles(gid)
      .then((r) => setColorRoles(r.color_roles ?? []))
      .catch(() => setColorRoles([]));
  }, [gid, tab]);

  if (autorole.loading || onboarding.loading) {
    if (autorole.verifying || onboarding.verifying) {
      return <LoadingCard label="verifying permissions…" />;
    }
    return <LoadingCard label="loading roles…" />;
  }
  if ((autorole.error && !autorole.settings) || (onboarding.error && !onboarding.settings)) {
    return <ErrorCard message={autorole.error ?? onboarding.error ?? 'failed to load'} />;
  }

  const a = (autorole.settings ?? {}) as Record<string, Settings[keyof Settings]>;
  const o = (onboarding.settings ?? {}) as Record<string, Settings[keyof Settings]>;

  return (
    <>
      <ModuleCard
        icon="sparkles"
        title="roles"
        description="autorole, self-roles, colors and onboarding — identity, softly arranged"
      >
        <Tabs
          tabs={[
            { id: 'autorole', label: 'autorole', icon: 'sparkles' },
            { id: 'selfroles', label: 'self-roles', icon: 'users' },
            { id: 'colors', label: 'color roles', icon: 'zap' },
            { id: 'onboarding', label: 'onboarding', icon: 'star' },
          ]}
          active={tab}
          onChange={setTab}
        />

        {tab === 'autorole' && (
          <Card id="autorole">
            <CardTitle icon="sparkles">autorole</CardTitle>
            <p className="mt-1.5 text-xs text-veloura-muted">
              granted automatically the moment a member joins
            </p>
            <div className="mt-4">
              <RolePicker
                id="autorole-role"
                label="join role"
                value={(a.role_id as string | null) ?? null}
                onChange={(v) => autorole.update({ role_id: v })}
              />
            </div>
            <Link
              href={`/servers/${gid}/leveling#rewards`}
              className="mt-4 inline-flex items-center gap-2 text-sm text-veloura-lavender transition hover:text-veloura-pink"
            >
              ✩ level rewards are managed on the leveling page →
            </Link>
          </Card>
        )}

        {tab === 'selfroles' && (
          <Card id="selfroles">
            <CardTitle icon="users">self-roles</CardTitle>
            <p className="mt-1.5 text-xs leading-relaxed text-veloura-muted">
              members pick their own roles with{' '}
              <code className="text-veloura-lavender">/selfroles</code>. panels are
              managed in discord with{' '}
              <code className="text-veloura-lavender">/selfroles panel</code> — what
              exists today:
            </p>
            <div className="mt-4">
              <SelfRolesInfo gid={gid} />
            </div>
          </Card>
        )}

        {tab === 'colors' && (
          <Card id="colors">
            <CardTitle icon="zap">color roles</CardTitle>
            <p className="mt-1.5 text-xs text-veloura-muted">
              personal colors chosen with <code className="text-veloura-lavender">/color set</code> —
              one per member, 24h between changes
            </p>
            <div className="mt-4">
              {colorRoles === null ? (
                <p className="text-sm text-veloura-muted">loading…</p>
              ) : colorRoles.length === 0 ? (
                <EmptyState icon="zap" title="no custom colors yet" hint="members create theirs with /color set #FFC0CB" />
              ) : (
                <ul className="divide-y divide-veloura-border/40">
                  {colorRoles.map((r) => (
                    <li key={`${r.user_id}-${r.role_id}`} className="flex items-center gap-3 py-2.5 text-sm">
                      <span
                        aria-hidden
                        className="h-4 w-4 shrink-0 rounded-full border border-veloura-border"
                        style={{ background: r.hex_color }}
                      />
                      <span className="text-veloura-text">{r.display_name}</span>
                      <span className="font-mono text-xs text-veloura-muted">{r.hex_color}</span>
                      <span className="ml-auto text-xs text-veloura-muted/60">
                        {timeAgo(r.last_changed)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        )}

        {tab === 'onboarding' && (
          <Card id="onboarding">
            <CardTitle icon="star">onboarding</CardTitle>
            <p className="mt-1.5 text-xs text-veloura-muted">
              a soft first message with role buttons for new members
            </p>
            <div className="mt-4">
              <div className="mb-4 flex items-center justify-between gap-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 px-4 py-3">
                <span className="text-sm text-veloura-text">onboarding enabled</span>
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-[#FFC0CB]"
                  checked={Boolean(o.enabled)}
                  onChange={(e) => onboarding.update({ enabled: e.target.checked })}
                  aria-label="enable onboarding"
                />
              </div>
              <MessageEditor
                label="welcome text"
                value={String(o.welcome_text ?? '')}
                onChange={(v) => onboarding.update({ welcome_text: v })}
                rows={4}
              />
              <RoleMultiPicker
                label="selectable roles"
                help="roles new members can choose — roles above aurelia can't be granted and are hidden"
                value={Array.isArray(o.roles) ? (o.roles as string[]) : []}
                onChange={(v) => onboarding.update({ roles: v })}
              />
            </div>
          </Card>
        )}
      </ModuleCard>

      {/* save bars per tab */}
      {tab === 'autorole' && (
        <SaveBar
          dirty={autorole.dirty}
          saving={autorole.saving}
          error={autorole.error}
          onSave={async () => {
            const ok = await autorole.save();
            if (ok) toast.push('autorole saved ✦', 'success');
          }}
          onRevert={autorole.revert}
        />
      )}
      {tab === 'onboarding' && (
        <SaveBar
          dirty={onboarding.dirty}
          saving={onboarding.saving}
          error={onboarding.error}
          onSave={async () => {
            const ok = await onboarding.save();
            if (ok) toast.push('onboarding saved ✦', 'success');
          }}
          onRevert={onboarding.revert}
          onResetDefaults={async () => {
            const ok = await onboarding.resetDefaults();
            if (ok) toast.push('reset to defaults', 'info');
          }}
        />
      )}
      {(tab === 'selfroles' || tab === 'colors') && (
        <p className="text-center text-xs text-veloura-muted/60">
          nothing to save on this tab ✧
        </p>
      )}
    </>
  );
}

/** self_role_panels: {panels: [...]} — read-only summary. */
function SelfRolesInfo({ gid }: { gid: string }) {
  const [panels, setPanels] = useState<unknown[] | null>(null);

  useEffect(() => {
    endpoints
      .settings(gid, 'self_roles')
      .then((r) => {
        const p = (r.settings as Record<string, unknown>)?.panels;
        setPanels(Array.isArray(p) ? (p as unknown[]) : []);
      })
      .catch(() => setPanels([]));
  }, [gid]);

  if (panels === null) return <p className="text-sm text-veloura-muted">loading…</p>;
  if (panels.length === 0) {
    return (
      <EmptyState
        icon="users"
        title="no self-role panels yet"
        hint="create one in discord with /selfroles panel — it appears here once saved"
      />
    );
  }
  return (
    <div className="space-y-2">
      {panels.map((p, i) => {
        const panel = p as Record<string, unknown>;
        const roles = (panel.roles ?? []) as { name?: string; label?: string }[];
        return (
          <div
            key={i}
            className="flex flex-wrap items-center gap-2 rounded-[12px] border border-veloura-border/50 bg-veloura-navy/50 px-3.5 py-2.5"
          >
            <span className="text-sm text-veloura-text">
              {String(panel.title ?? `panel ${i + 1}`)}
            </span>
            <Badge tone="muted">{roles.length} roles</Badge>
          </div>
        );
      })}
    </div>
  );
}
