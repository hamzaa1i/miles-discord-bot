'use client';

/** Custom commands — table, add/edit/delete with variable helper. */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { Card, CardTitle, Badge, LoadingCard, TextInput } from '@/components/ui/primitives';
import { EmptyState, SectionHeading } from '@/components/EmptyState';
import { MessageEditor } from '@/components/MessageEditor';
import { useToast } from '@/components/ui/toast';
import { truncate } from '@/lib/format';
import type { CustomCommand } from '@/lib/types';

export default function CustomCommandsPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const toast = useToast();

  const [commands, setCommands] = useState<CustomCommand[] | null>(null);
  const [editing, setEditing] = useState<CustomCommand | null>(null);
  const [trigger, setTrigger] = useState('');
  const [response, setResponse] = useState('');
  const [saving, setSaving] = useState(false);

  function reload() {
    endpoints
      .customCommands(gid)
      .then((r) => setCommands(r.custom_commands ?? []))
      .catch(() => setCommands([]));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gid]);

  function startEdit(c: CustomCommand) {
    setEditing(c);
    setTrigger(c.trigger);
    setResponse(c.response);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function startNew() {
    setEditing({ trigger: '', response: '' });
    setTrigger('');
    setResponse('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function save() {
    const t = trigger.trim().toLowerCase();
    if (!t || !response.trim()) {
      toast.push('both trigger and response are needed ✧', 'error');
      return;
    }
    setSaving(true);
    try {
      const list = (commands ?? []).filter((c) => c.trigger !== t);
      list.push({ trigger: t, response: response.trim() });
      await endpoints.patchSettings(gid, 'custom_commands', { commands: list });
      setEditing(null);
      setTrigger('');
      setResponse('');
      reload();
      toast.push(`command "${t}" saved ✦`, 'success');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'save failed', 'error');
    } finally {
      setSaving(false);
    }
  }

  async function remove(c: CustomCommand) {
    try {
      await endpoints.deleteData(gid, 'custom_commands', c.trigger);
      setCommands((cs) => (cs ?? []).filter((x) => x.trigger !== c.trigger));
      if (editing?.trigger === c.trigger) setEditing(null);
      toast.push(`command "${c.trigger}" removed`, 'info');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'delete failed', 'error');
    }
  }

  return (
    <>
      <ModuleCard
        icon="✧"
        title="custom commands"
        description="your own little spells — a trigger word, an enchanted response"
      >
        {editing ? (
          <Card className="border-veloura-pink/40">
            <CardTitle icon={editing.trigger ? '✎' : '✦'}>
              {editing.trigger ? `edit "${editing.trigger}"` : 'new command'}
            </CardTitle>
            <div className="mt-4">
              <div className="mb-4">
                <label htmlFor="cc-trigger" className="veloura-label">
                  trigger — typed in chat
                </label>
                <TextInput
                  id="cc-trigger"
                  placeholder="hug"
                  maxLength={32}
                  value={trigger}
                  onChange={(e) => setTrigger(e.target.value)}
                />
              </div>
              <MessageEditor
                id="cc-response"
                label="response"
                help="members type the trigger and aurelia replies with this"
                value={response}
                onChange={setResponse}
                rows={4}
              />
            </div>
            <div className="mt-4 flex gap-2">
              <button onClick={save} disabled={saving} className="veloura-button-primary">
                {saving ? 'saving…' : '✦ save command'}
              </button>
              <button onClick={() => setEditing(null)} className="veloura-button-ghost">
                cancel
              </button>
            </div>
          </Card>
        ) : (
          <button onClick={startNew} className="veloura-button-primary">
            ✦ new command
          </button>
        )}

        <SectionHeading icon="✧" right={<Badge tone="muted">{commands?.length ?? 0} commands</Badge>}>
          your commands
        </SectionHeading>

        {commands === null ? (
          <LoadingCard label="loading commands…" />
        ) : commands.length === 0 ? (
          <EmptyState
            icon="✧"
            title="no custom commands yet"
            hint="create one above — it responds instantly, no AI call needed"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="border-b border-veloura-border/60 text-left text-xs uppercase tracking-wider text-veloura-muted">
                  <th className="pb-2 pr-4">trigger</th>
                  <th className="pb-2 pr-4">response</th>
                  <th className="pb-2 text-right">actions</th>
                </tr>
              </thead>
              <tbody>
                {commands.map((c) => (
                  <tr key={c.trigger} className="border-b border-veloura-border/30">
                    <td className="py-3 pr-4">
                      <code className="rounded bg-veloura-navy px-2 py-0.5 font-mono text-xs text-veloura-lavender">
                        {c.trigger}
                      </code>
                    </td>
                    <td className="max-w-[320px] truncate py-3 pr-4 text-veloura-muted">
                      {truncate(c.response, 64)}
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end gap-1.5">
                        <button
                          onClick={() => startEdit(c)}
                          className="rounded-[10px] border border-veloura-border px-2.5 py-1 text-xs text-veloura-lavender transition hover:bg-veloura-card-hover"
                        >
                          ✎ edit
                        </button>
                        <button
                          onClick={() => remove(c)}
                          className="rounded-[10px] border border-veloura-danger/30 px-2.5 py-1 text-xs text-veloura-danger transition hover:bg-veloura-danger/10"
                        >
                          ✕
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ModuleCard>
    </>
  );
}
