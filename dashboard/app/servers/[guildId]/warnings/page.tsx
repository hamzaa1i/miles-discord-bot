'use client';

/**
 * Warnings — the guild's case history: searchable, paginated, live.
 * Split out of the moderation settings page so "warnings" is its own
 * route (sidebar item highlights exactly here, deep-linkable).
 */

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, Badge, TextInput, ErrorCard } from '@/components/ui/primitives';
import { EmptyState } from '@/components/EmptyState';
import { useToast } from '@/components/ui/toast';
import { useRealtime } from '@/lib/useRealtime';
import { timeAgo } from '@/lib/format';
import type { Warning } from '@/lib/types';
import { Icon } from '@/components/icons';

export default function WarningsPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();

  const [warnings, setWarnings] = useState<Warning[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const perPage = 20;

  const loadWarnings = useCallback(
    (p = page, user = query) => {
      endpoints
        .warnings(gid, p, perPage, user || undefined)
        .then((r) => {
          setWarnings(r.warnings);
          setTotal(r.total);
          setError(null);
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : 'could not load warnings');
          setWarnings([]);
        });
    },
    [gid, page, query],
  );

  useEffect(() => {
    loadWarnings();
  }, [loadWarnings]);

  // realtime: new warnings pop in with a toast
  const { live } = useRealtime(gid, 'warnings', () => {
    setPage(1);
    loadWarnings(1, query);
    toast.push('new warning recorded ✧', 'info');
  });

  async function deleteWarning(w: Warning) {
    const id = String(w.id ?? w.case_id ?? '');
    setDeleting(id);
    try {
      await endpoints.deleteData(gid, 'warnings', id);
      setWarnings((ws) => (ws ?? []).filter((x) => String(x.id ?? x.case_id) !== id));
      setTotal((t) => Math.max(0, t - 1));
      toast.push('warning deleted', 'info');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'delete failed', 'error');
    } finally {
      setDeleting(null);
    }
  }

  if (error && !warnings) return <ErrorCard message={error} />;

  const pages = Math.max(1, Math.ceil(total / perPage));

  return (
    <ModuleCard
      icon="swords"
      title="warnings"
      description="the case history — searchable, paginated, updated live"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Badge tone="lavender">
          {total} {total === 1 ? 'record' : 'records'}
        </Badge>
        <Link
          href={`/servers/${gid}/moderation`}
          className="text-xs text-veloura-lavender transition hover:text-veloura-pink"
        >
          thresholds &amp; actions live on the moderation page →
        </Link>
      </div>

      {warnings === null ? (
        <p className="text-sm text-veloura-muted">loading…</p>
      ) : warnings.length === 0 ? (
        <EmptyState
          icon="sparkles"
          title={query ? 'no warnings match that filter' : 'no warnings found'}
          hint={
            query
              ? 'try clearing the user filter'
              : 'a clean record — warnings appear here the moment mods issue them'
          }
        />
      ) : (
        <Card>
          <div className="mb-4">
            <form
              className="flex flex-1 gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setPage(1);
                loadWarnings(1, query);
              }}
            >
              <TextInput
                placeholder="filter by user id…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="filter warnings by user id"
              />
              <button type="submit" className="veloura-button-ghost shrink-0 !min-h-[44px]">
                search
              </button>
            </form>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-veloura-border/60 text-left text-xs uppercase tracking-wider text-veloura-muted">
                  <th className="pb-2 pr-4">user</th>
                  <th className="pb-2 pr-4">reason</th>
                  <th className="pb-2 pr-4">by</th>
                  <th className="pb-2 pr-4">when</th>
                  <th className="pb-2 text-right">remove</th>
                </tr>
              </thead>
              <tbody>
                {warnings.map((w, i) => (
                  <tr key={String(w.id ?? w.case_id ?? i)} className="border-b border-veloura-border/30">
                    <td className="py-3 pr-4">
                      <span className="font-mono text-xs text-veloura-lavender">
                        {w.user_id.slice(0, 10)}…
                      </span>
                    </td>
                    <td className="max-w-[240px] truncate py-3 pr-4 text-veloura-text">
                      {w.reason ?? '—'}
                    </td>
                    <td className="py-3 pr-4 text-xs text-veloura-muted">{w.mod_name ?? '—'}</td>
                    <td className="py-3 pr-4 text-xs text-veloura-muted/70">
                      {timeAgo(w.timestamp)}
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => deleteWarning(w)}
                        disabled={deleting !== null}
                        className="flex h-11 w-11 items-center justify-center rounded-[10px] border border-veloura-danger/30 text-veloura-danger transition hover:bg-veloura-danger/10 disabled:opacity-50"
                        aria-label="delete warning"
                      >
                        <Icon name="trash" size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="veloura-button-ghost !min-h-[36px] px-3 text-xs"
              >
                ← prev
              </button>
              <span className="text-xs text-veloura-muted">
                page {page} / {pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                disabled={page >= pages}
                className="veloura-button-ghost !min-h-[36px] px-3 text-xs"
              >
                next →
              </button>
            </div>
          )}
        </Card>
      )}

      {live && (
        <p className="mt-3 text-center text-xs text-veloura-muted/60">
          listening for new warnings in realtime ✧
        </p>
      )}
    </ModuleCard>
  );
}
