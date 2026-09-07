'use client';

/**
 * Reminders — the CALLER's personal /remind list.
 *
 * /remind is a per-user bot command, not guild configuration: reminders
 * belong to the Discord account, fire in DMs or the channel they were
 * created in, and only the owner sees them here. This page lists them
 * live from the bot's reminders store and lets the owner cancel any.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints, ApiRequestError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, Badge, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { EmptyState } from '@/components/EmptyState';
import { Icon } from '@/components/icons';
import { useToast } from '@/components/ui/toast';
import type { ReminderRow } from '@/lib/types';

function untilLabel(endTime: number | null): string {
  if (!endTime) return '—';
  const diff = endTime * 1000 - Date.now();
  if (diff <= 0) return 'firing soon';
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `in ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `in ${hours}h ${mins % 60}m`;
  const days = Math.floor(hours / 24);
  return `in ${days}d ${hours % 24}h`;
}

export default function RemindersPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  void gid; // reminders are user-scoped; guild context is only for the shell
  const { user } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<ReminderRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    endpoints
      .reminders()
      .then((r) => setRows(r.reminders ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : 'could not load reminders'));
  }, []);

  async function remove(row: ReminderRow) {
    setDeleting(row.id);
    try {
      await endpoints.deleteReminder(row.id);
      setRows((rs) => (rs ?? []).filter((r) => r.id !== row.id));
      toast.push('reminder cancelled', 'info');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'could not cancel', 'error');
    } finally {
      setDeleting(null);
    }
  }

  return (
    <ModuleCard
      icon="timer"
      title="reminders"
      description="your own /remind list — personal, not server config"
    >
      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-veloura-muted">
          <span className="flex items-center gap-1.5">
            <Icon name="timer" size={13} className="text-veloura-pink" />
            create with{' '}
            <code className="text-veloura-lavender">/remind create what:… when:30m</code>
          </span>
          <span className="flex items-center gap-1.5">
            <Icon name="refresh" size={13} className="text-veloura-lavender" />
            recurring:{' '}
            <code className="text-veloura-lavender">daily · weekly · monthly</code>
          </span>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-veloura-muted/70">
          reminders are per-user — they follow your discord account across
          servers and fire in the channel they were created in (or your dms).
          {user ? ` this list belongs to ${user.display_name}.` : ''} server staff
          can&apos;t see or manage other members&apos; reminders by design.
        </p>
      </Card>

      {error ? (
        <ErrorCard message={error} />
      ) : rows === null ? (
        <LoadingCard label="gathering your reminders…" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon="timer"
          title="no active reminders"
          hint="create one in discord with /remind create — it appears here instantly"
        />
      ) : (
        <Card>
          <ul className="divide-y divide-veloura-border/40">
            {rows.map((r) => (
              <li key={r.id} className="flex items-center gap-3 py-3 text-sm">
                <span className="min-w-0 flex-1 truncate text-veloura-text">{r.text}</span>
                {r.repeat !== 'none' && <Badge tone="lavender">{r.repeat}</Badge>}
                <span className="shrink-0 text-xs text-veloura-muted/70">
                  {untilLabel(r.end_time)}
                </span>
                <button
                  onClick={() => remove(r)}
                  disabled={deleting === r.id}
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] border border-veloura-danger/30 text-veloura-danger transition hover:bg-veloura-danger/10 disabled:opacity-50"
                  aria-label={`cancel reminder: ${r.text}`}
                >
                  <Icon name="trash" size={15} />
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-veloura-muted/60">
            {rows.length} active — cancel any with the button; recurring
            reminders restart from their next scheduled fire.
          </p>
        </Card>
      )}
    </ModuleCard>
  );
}
