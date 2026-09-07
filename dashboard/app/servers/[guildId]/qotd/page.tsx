'use client';

/** QOTD — schedule, custom question queue, post now, history. */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker } from '@/components/ChannelPicker';
import { Card, CardTitle, Badge, LoadingCard, ErrorCard, TextInput } from '@/components/ui/primitives';
import { EmptyState, SectionHeading } from '@/components/EmptyState';
import { useToast } from '@/components/ui/toast';
import { timeAgo, cn } from '@/lib/format';
import type { QotdQueueRow, Settings } from '@/lib/types';

const DEFAULTS: Settings = {
  enabled: false,
  channel_id: null,
  post_hour_utc: 14,
  auto_thread: true,
};

export default function QotdPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();
  const ms = useModuleSettings(gid, 'qotd', DEFAULTS);
  const [queue, setQueue] = useState<QotdQueueRow[] | null>(null);
  const [newQuestion, setNewQuestion] = useState('');
  const [posting, setPosting] = useState(false);
  const [adding, setAdding] = useState(false);

  const reloadQueue = () => {
    endpoints
      .qotdQueue(gid)
      .then((r) => setQueue(r.queue ?? []))
      .catch(() => setQueue([]));
  };

  useEffect(() => {
    reloadQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gid, ms.saved]);

  if (ms.loading) return <LoadingCard label="loading qotd config…" />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;
  const hour = Number(s.post_hour_utc ?? 14);
  const unused = (queue ?? []).filter((q) => !q.used);
  const history = (queue ?? []).filter((q) => q.used);

  async function postNow() {
    setPosting(true);
    try {
      await endpoints.action(gid, 'qotd_post_now');
      toast.push('qotd queued — watch the channel ✦', 'success');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'failed to queue', 'error');
    } finally {
      setPosting(false);
    }
  }

  async function addQuestion() {
    const q = newQuestion.trim();
    if (!q) return;
    setAdding(true);
    try {
      await endpoints.action(gid, 'qotd_add', { question: q });
      setNewQuestion('');
      toast.push('question added to the queue ✦', 'success');
      setTimeout(reloadQueue, 2500); // action executes on the bot within ~5s
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'failed to add', 'error');
    } finally {
      setAdding(false);
    }
  }

  async function removeQuestion(row: QotdQueueRow) {
    const id = String(row.id ?? row.question);
    try {
      await endpoints.deleteData(gid, 'qotd_queue', id);
      setQueue((q) => (q ?? []).filter((x) => String(x.id ?? x.question) !== id));
      toast.push('question removed', 'info');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'failed to remove', 'error');
    }
  }

  return (
    <>
      <ModuleCard
        icon="❓"
        title="qotd"
        description="one question a day, gently placed — with a thread to gather the answers"
        enabled={Boolean(s.enabled)}
        onToggle={async (next) => {
          ms.update({ enabled: next });
          const ok = await ms.patch({ enabled: next });
          if (ok) toast.push(`qotd ${next ? 'enabled' : 'disabled'} ✦`, 'success');
        }}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle icon="✦">schedule</CardTitle>
            <div className="mt-4">
              <ChannelPicker
                id="qotd-channel"
                label="question channel"
                value={s.channel_id as string | null}
                onChange={(v) => ms.update({ channel_id: v })}
              />
              <div className="mb-6">
                <label htmlFor="post-hour" className="veloura-label">
                  post hour (utc)
                </label>
                <div className="flex items-center gap-4">
                  <input
                    id="post-hour"
                    type="range"
                    min={0}
                    max={23}
                    step={1}
                    value={hour}
                    onChange={(e) => ms.update({ post_hour_utc: Number(e.target.value) })}
                    className="flex-1"
                  />
                  <Badge tone="pink">{String(hour).padStart(2, '0')}:00 utc</Badge>
                </div>
                <p className="mt-2 text-xs text-veloura-muted/80">
                  the question posts once a day, at or after this hour
                </p>
              </div>
              <div className="mb-2 flex items-center justify-between gap-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 px-4 py-3">
                <div>
                  <p className="text-sm text-veloura-text">auto-thread</p>
                  <p className="text-xs text-veloura-muted/70">open a thread for answers</p>
                </div>
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-[#FFC0CB]"
                  checked={Boolean(s.auto_thread)}
                  onChange={(e) => ms.update({ auto_thread: e.target.checked })}
                  aria-label="auto thread"
                />
              </div>
            </div>
          </Card>

          <Card className="flex flex-col">
            <CardTitle icon="✧">custom questions</CardTitle>
            <p className="mt-1.5 text-xs text-veloura-muted">
              asked before the built-in pool — {unused.length} waiting
            </p>
            <div className="mt-4 flex-1">
              {unused.length > 0 ? (
                <ul className="max-h-64 space-y-2 overflow-y-auto pr-1">
                  {unused.map((q, i) => (
                    <li
                      key={String(q.id ?? i)}
                      className="flex items-start justify-between gap-3 rounded-[12px] border border-veloura-border/50 bg-veloura-navy/50 px-3.5 py-2.5"
                    >
                      <span className="text-sm leading-relaxed text-veloura-text">{q.question}</span>
                      <button
                        onClick={() => removeQuestion(q)}
                        className="shrink-0 rounded-full border border-veloura-danger/30 px-2 py-0.5 text-xs text-veloura-danger transition hover:bg-veloura-danger/10"
                        aria-label="remove question"
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  icon="❓"
                  title="queue is empty"
                  hint="add questions below — otherwise aurelia draws from her own pool of 40"
                />
              )}
            </div>
            <div className="mt-4">
              <label htmlFor="new-question" className="veloura-label">
                add a question
              </label>
              <div className="flex gap-2">
                <TextInput
                  id="new-question"
                  placeholder="what's the softest sound you know?"
                  maxLength={300}
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                />
                <button
                  onClick={addQuestion}
                  disabled={adding || !newQuestion.trim()}
                  className="veloura-button-primary shrink-0"
                >
                  {adding ? '…' : '✦ add'}
                </button>
              </div>
            </div>
          </Card>
        </div>

        <button
          onClick={postNow}
          disabled={posting || !s.channel_id}
          className="veloura-button-primary mt-6 w-full sm:w-auto"
          title={s.channel_id ? undefined : 'set a channel first'}
        >
          {posting ? 'queuing…' : '❓ post now'}
        </button>
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('qotd config saved ✦', 'success');
        }}
        onRevert={ms.revert}
        onResetDefaults={async () => {
          const ok = await ms.resetDefaults();
          if (ok) toast.push('reset to defaults', 'info');
        }}
      />

      <SectionHeading icon="📜">question history</SectionHeading>
      <Card>
        {history.length > 0 ? (
          <ul className="divide-y divide-veloura-border/40">
            {history.slice(0, 20).map((q, i) => (
              <li key={String(q.id ?? i)} className="flex items-center gap-3 py-2.5 text-sm">
                <span className={cn('flex-1 text-veloura-muted')}>{q.question}</span>
                <span className="shrink-0 text-xs text-veloura-muted/60">
                  {timeAgo(q.added_at)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState icon="✧" title="no questions asked yet" hint="history appears here after the first post" />
        )}
      </Card>
    </>
  );
}
