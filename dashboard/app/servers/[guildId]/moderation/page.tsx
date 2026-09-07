'use client';

/** Moderation — settings + searchable, paginated warnings with realtime. */

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker, RolePicker, ChannelMultiPicker } from '@/components/ChannelPicker';
import { Card, CardTitle, Badge, Select, TextInput, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { EmptyState, SectionHeading } from '@/components/EmptyState';
import { useToast } from '@/components/ui/toast';
import { useRealtime } from '@/lib/useRealtime';
import { timeAgo } from '@/lib/format';
import type { Settings, Warning } from '@/lib/types';
import { Icon } from '@/components/icons';

const DEFAULTS: Settings = {
  log_channel_id: null,
  admin_role_id: null,
  max_warns_before_ban: 3,
  warn_threshold_count: 3,
  warn_threshold_action: 'timeout',
  antispam_enabled: false,
  antilink_channels: null,
};

const THRESHOLD_ACTIONS = [
  { value: 'timeout', label: 'timeout' },
  { value: 'kick', label: 'kick' },
  { value: 'ban', label: 'ban' },
];

export default function ModerationPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ms = useModuleSettings(gid, 'moderation', DEFAULTS);

  const [warnings, setWarnings] = useState<Warning[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [userFilter, setUserFilter] = useState('');
  const [query, setQuery] = useState('');
  const perPage = 20;

  const loadWarnings = useCallback(
    (p = page, user = query) => {
      endpoints
        .warnings(gid, p, perPage, user || undefined)
        .then((r) => {
          setWarnings(r.warnings);
          setTotal(r.total);
        })
        .catch(() => setWarnings([]));
    },
    [gid, page, query],
  );

  useEffect(() => {
    loadWarnings();
  }, [loadWarnings]);

  // realtime: new warnings pop in with a badge
  const { live } = useRealtime(gid, 'warnings', () => {
    setPage(1);
    loadWarnings(1, query);
    toast.push('new warning recorded ✧', 'info');
  });

  async function deleteWarning(w: Warning) {
    const id = String(w.id ?? w.case_id ?? '');
    try {
      await endpoints.deleteData(gid, 'warnings', id);
      setWarnings((ws) => (ws ?? []).filter((x) => String(x.id ?? x.case_id) !== id));
      setTotal((t) => Math.max(0, t - 1));
      toast.push('warning deleted', 'info');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'delete failed', 'error');
    }
  }

  if (ms.loading)
    return <LoadingCard label={ms.verifying ? 'verifying permissions…' : 'loading moderation config…'} />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;
  const pages = Math.max(1, Math.ceil(total / perPage));

  return (
    <>
      <ModuleCard
        icon="swords"
        title="moderation"
        description="warnings, thresholds and the quiet guardrails"
        enabled={Boolean(s.antispam_enabled)}
        toggledLabel="antispam on"
        onToggle={async (next) => {
          ms.update({ antispam_enabled: next });
          const ok = await ms.patch({ antispam_enabled: next });
          if (ok) toast.push(`antispam ${next ? 'enabled' : 'disabled'} ✦`, 'success');
        }}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle icon="users">roles &amp; logs</CardTitle>
            <div className="mt-4">
              <ChannelPicker
                id="mod-log"
                label="moderation log channel"
                value={s.log_channel_id as string | null}
                onChange={(v) => ms.update({ log_channel_id: v })}
              />
              <RolePicker
                id="admin-role"
                label="admin role"
                help="members who can use moderation commands"
                value={s.admin_role_id as string | null}
                onChange={(v) => ms.update({ admin_role_id: v })}
              />
            </div>
          </Card>

          <Card>
            <CardTitle icon="swords">warning threshold</CardTitle>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div className="mb-4">
                <label htmlFor="threshold-count" className="veloura-label">
                  warn count
                </label>
                <TextInput
                  id="threshold-count"
                  type="number"
                  min={1}
                  max={10}
                  value={String(s.warn_threshold_count ?? 3)}
                  onChange={(e) => ms.update({ warn_threshold_count: Number(e.target.value) || 3 })}
                />
              </div>
              <div className="mb-4">
                <label htmlFor="threshold-action" className="veloura-label">
                  action
                </label>
                <Select
                  id="threshold-action"
                  value={String(s.warn_threshold_action ?? 'timeout')}
                  onChange={(e) => ms.update({ warn_threshold_action: e.target.value })}
                >
                  {THRESHOLD_ACTIONS.map((a) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="mb-4">
              <label htmlFor="max-warns" className="veloura-label">
                max warns before ban
              </label>
              <TextInput
                id="max-warns"
                type="number"
                min={1}
                max={20}
                value={String(s.max_warns_before_ban ?? 3)}
                onChange={(e) => ms.update({ max_warns_before_ban: Number(e.target.value) || 3 })}
              />
            </div>
            <ChannelMultiPicker
              label="antilink channels"
              help="links are removed in these channels"
              value={Array.isArray(s.antilink_channels) ? (s.antilink_channels as string[]) : []}
              onChange={(v) => ms.update({ antilink_channels: v.length ? v : null })}
            />
          </Card>
        </div>
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('moderation config saved ✦', 'success');
        }}
        onRevert={ms.revert}
      />

      <SectionHeading icon="scroll" right={live ? <Badge tone="success">realtime</Badge> : undefined}>
        warnings <span className="text-sm text-veloura-muted">({total})</span>
      </SectionHeading>
      <Card id="warnings">
        <div className="mb-4 flex flex-wrap gap-2">
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
              onChange={(e) => {
                setQuery(e.target.value);
                setUserFilter(e.target.value);
              }}
              aria-label="filter warnings by user id"
            />
            <button type="submit" className="veloura-button-ghost shrink-0 !min-h-[44px]">
              search
            </button>
          </form>
        </div>

        {warnings === null ? (
          <p className="text-sm text-veloura-muted">loading…</p>
        ) : warnings.length === 0 ? (
          <EmptyState
            icon="sparkles"
            title="no warnings found"
            hint="a clean record — or none matching this filter"
          />
        ) : (
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
                        className="flex h-11 w-11 items-center justify-center rounded-[10px] border border-veloura-danger/30 text-veloura-danger transition hover:bg-veloura-danger/10"
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
        )}

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
    </>
  );
}
