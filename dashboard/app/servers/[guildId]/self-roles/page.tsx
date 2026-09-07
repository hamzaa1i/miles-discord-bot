'use client';

/**
 * Self-roles — read-only panel summary.
 *
 * Panels are created and managed entirely in Discord with
 * /selfroles panel — there is nothing to configure here, so this page
 * has NO save bar: it shows what exists and points to the command.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge } from '@/components/ui/primitives';
import { EmptyState } from '@/components/EmptyState';

export default function SelfRolesPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
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

  return (
    <ModuleCard
      icon="users"
      title="self-roles"
      description="members pick their own roles from panels in discord"
    >
      <Card>
        <CardTitle icon="users">panels</CardTitle>
        <p className="mt-1.5 text-xs leading-relaxed text-veloura-muted">
          self-roles are managed with{' '}
          <code className="text-veloura-lavender">/selfroles panel</code> in discord ✦ —
          build the panel, add roles, and aurelia posts the message with buttons.
          what exists today:
        </p>
        <div className="mt-4">
          {panels === null ? (
            <p className="text-sm text-veloura-muted">loading…</p>
          ) : panels.length === 0 ? (
            <EmptyState
              icon="users"
              title="no self-role panels yet"
              hint="create one in discord with /selfroles panel — it appears here once saved"
            />
          ) : (
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
          )}
        </div>
      </Card>

      <p className="mt-4 text-center text-xs text-veloura-muted/60">
        nothing to save here — panel changes happen in discord with{' '}
        <code className="text-veloura-lavender">/selfroles panel</code> and sync instantly
      </p>
    </ModuleCard>
  );
}
