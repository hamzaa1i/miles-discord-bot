'use client';

/** AuditList — recent dashboard mutations (from dashboard_audit). */

import { Badge } from './ui/primitives';
import { timeAgo, cn } from '@/lib/format';
import type { AuditEntry } from '@/lib/types';

const ACTION_TONES: Record<string, 'pink' | 'lavender' | 'success' | 'danger' | 'muted'> = {
  settings_patch: 'pink',
  action_qotd_post_now: 'lavender',
  action_welcome_test: 'lavender',
  action_giveaway_end: 'danger',
  data_delete: 'danger',
  oauth_login: 'muted',
};

export function AuditList({ entries, limit = 10 }: { entries: AuditEntry[]; limit?: number }) {
  if (entries.length === 0) {
    return (
      <p className="px-1 text-sm text-veloura-muted/70">
        no dashboard activity yet — changes you make will appear here ✧
      </p>
    );
  }

  return (
    <ul className="divide-y divide-veloura-border/50">
      {entries.slice(0, limit).map((e, i) => (
        <li key={e.id ?? i} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-sm">
          <Badge tone={ACTION_TONES[e.action] ?? 'default'}>{e.action}</Badge>
          <span className="font-mono text-xs text-veloura-muted">
            user {e.user_id.slice(0, 8)}…
          </span>
          {e.details && (
            <span className="min-w-0 flex-1 truncate text-xs text-veloura-muted/70">
              {e.details}
            </span>
          )}
          <span className={cn('ml-auto shrink-0 text-xs text-veloura-muted/60')}>
            {timeAgo(e.timestamp)}
          </span>
        </li>
      ))}
    </ul>
  );
}
