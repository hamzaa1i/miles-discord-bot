'use client';

/**
 * Color roles — read-only list of member-chosen personal colors.
 *
 * Colors are set by members themselves with /color set — nothing is
 * configurable from the dashboard, so no save bar: the list shows who
 * wears what, and the command pointer explains why.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle } from '@/components/ui/primitives';
import { EmptyState } from '@/components/EmptyState';
import { timeAgo } from '@/lib/format';
import type { ColorRoleRow } from '@/lib/types';

export default function ColorRolesPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const [rows, setRows] = useState<ColorRoleRow[] | null>(null);

  useEffect(() => {
    endpoints
      .colorRoles(gid)
      .then((r) => setRows(r.color_roles ?? []))
      .catch(() => setRows([]));
  }, [gid]);

  return (
    <ModuleCard
      icon="zap"
      title="color roles"
      description="personal colors chosen by members with /color set"
    >
      <Card>
        <CardTitle icon="zap">who wears what</CardTitle>
        <p className="mt-1.5 text-xs leading-relaxed text-veloura-muted">
          one personal color per member, 24h between changes — members create
          and update theirs in discord with{' '}
          <code className="text-veloura-lavender">/color set</code> ✦
        </p>
        <div className="mt-4">
          {rows === null ? (
            <p className="text-sm text-veloura-muted">loading…</p>
          ) : rows.length === 0 ? (
            <EmptyState
              icon="zap"
              title="no custom colors yet"
              hint="members create theirs with /color set #FFC0CB — the list fills in here as they do"
            />
          ) : (
            <ul className="divide-y divide-veloura-border/40">
              {rows.map((r) => (
                <li
                  key={`${r.user_id}-${r.role_id}`}
                  className="flex items-center gap-3 py-2.5 text-sm"
                >
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

      <p className="mt-4 text-center text-xs text-veloura-muted/60">
        nothing to save here — colors belong to each member and change only via{' '}
        <code className="text-veloura-lavender">/color set</code> in discord
      </p>
    </ModuleCard>
  );
}
