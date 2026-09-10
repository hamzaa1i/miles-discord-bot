'use client';

/**
 * Boosters module — PHASE O — the server booster system page.
 *
 * Announcement config (channel / message / mode / color / image /
 * footer / thumbnail), booster role management (auto-role, remove on
 * unboost), milestones (toggle + thresholds + message), a live preview
 * with the REAL current boost count, a safe test action and a reset
 * action (both run on the bot loop via the dashboard action queue).
 *
 * The role picker only lists roles aurelia can actually manage — the
 * backend filters managed/integration roles (incl. Discord's native
 * Server Booster role) and roles above the bot; the PATCH re-validates
 * server-side.
 */

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { useAuth } from '@/lib/auth';
import { useGuild } from '@/lib/guild';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker, RolePicker } from '@/components/ChannelPicker';
import { ColorPicker } from '@/components/ColorPicker';
import { MessageEditor } from '@/components/MessageEditor';
import { Card, CardTitle, Select, TextInput, Tabs, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import { defaultAvatar } from '@/lib/discord';
import type { Settings } from '@/lib/types';

const DEFAULT_MESSAGE = [
  '✩ ━━ **a new star is shining brighter** ༉‧₊˚. ღ',
  '',
  '꒰ა ♡ ໒꒱ thank you {user} for boosting **{server}**!',
  '',
  'your support helps our little community grow and unlock even more for everyone here.',
  '',
  "୨୧ you're officially one of our boosters",
  '୨୧ your booster perks are now available',
  '୨୧ thank you for supporting the community ♡',
  '',
  '𓂃 ࣪˖ ִֶָ **{boostcount} boosts** ִֶָ˖ ࣪ 𓂃',
  '',
  '✩ ━━ **thank you for supporting {server}** ༉‧₊˚. ღ',
].join('\n');

const DEFAULT_MILESTONE_MESSAGE = [
  '✩ ━━ **{server} reached {boostcount} boosts** ༉‧₊˚. ღ',
  '',
  'another little milestone reached ♡',
  'thank you to everyone supporting **{server}**.',
].join('\n');

const DEFAULTS: Settings = {
  enabled: false,
  channel_id: null,
  message: DEFAULT_MESSAGE,
  embed_mode: 'embed',
  color: '#FFC0CB',
  image_url: null,
  thumbnail_mode: 'member',
  footer: '{boostcount} boosts ♡',
  booster_role_id: null,
  auto_role: false,
  remove_role_on_unboost: true,
  milestone_enabled: true,
  milestone_message: DEFAULT_MILESTONE_MESSAGE,
  milestone_counts: [2, 7, 14],
  milestone_last: 0,
};

function normalizeColor(raw: string): string {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(raw.trim());
  return m ? `#${m[1]}` : '#FFC0CB';
}

interface PreviewContext {
  username: string;
  serverName: string;
  boostcount: number;
  avatar: string;
}

function substitute(template: string, ctx: PreviewContext): string {
  return String(template ?? '')
    .replaceAll('{user}', `@${ctx.username}`)
    .replaceAll('{user.name}', ctx.username)
    .replaceAll('{user.display_name}', ctx.username)
    .replaceAll('{user.id}', '123456789012345678')
    .replaceAll('{user.avatar}', ctx.avatar)
    .replaceAll('{server}', ctx.serverName)
    .replaceAll('{server.id}', '111222333444555666')
    .replaceAll('{server.icon}', ctx.avatar)
    .replaceAll('{boostcount}', String(ctx.boostcount))
    .replaceAll('{boostlevel}', '2')
    .replaceAll('\\n', '\n');
}

/**
 * Pure preview computation — deliberately NOT memoized.
 *
 * It only runs once settings are loaded, it is a handful of string
 * replaces (cheap), and putting a useMemo here would place a hook
 * below the loading/error early-returns: the loading render would call
 * 8 hooks while the loaded render calls 9, React would throw
 * "Rendered more hooks than during the previous render" (minified
 * React error #310) and the whole page crashes in production.
 */
function buildPreview(
  rawMessage: string,
  rawFooter: string,
  mode: string,
  ctx: PreviewContext,
): { content: string | null; body: string; footer: string } {
  const full = substitute(rawMessage, ctx);
  const footer = substitute(rawFooter, ctx);
  let content: string | null = null;
  let body: string = full;
  if (mode === 'text') {
    content = full;
  } else if (mode === 'hybrid' && full.includes('---')) {
    const [before, after] = full.split('---');
    content = before.trim();
    body = after.trim();
  }
  return { content, body, footer };
}

export default function BoostersPage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const { user } = useAuth();
  const toast = useToast();
  const { resources, overview } = useGuild();
  const ms = useModuleSettings(gid, 'boosters', DEFAULTS);
  const [tab, setTab] = useState('announcement');
  const [testing, setTesting] = useState(false);
  const [confirmingReset, setConfirmingReset] = useState(false);

  if (ms.loading)
    return <LoadingCard label={ms.verifying ? 'verifying permissions…' : 'loading booster config…'} />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;

  const previewCtx = {
    username: user?.display_name ?? 'a kind booster',
    serverName: overview?.name ?? 'your server',
    boostcount: resources?.boost_count ?? overview?.boost_count ?? 7,
    avatar: user?.avatar ?? defaultAvatar(user?.id ?? '0'),
  };

  async function runAction(action: 'booster_test' | 'booster_reset', successMsg: string) {
    setTesting(true);
    try {
      await endpoints.action(gid, action, {});
      toast.push(successMsg, 'success');
      if (action === 'booster_reset') {
        await ms.patch({ ...DEFAULTS });
      }
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'action failed', 'error');
    } finally {
      setTesting(false);
    }
  }

  function toggleRow(label: string, checked: boolean, onChange: (v: boolean) => void, help?: string) {
    return (
      <div className="mb-4 flex items-center justify-between gap-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 px-4 py-3">
        <div>
          <span className="text-sm text-veloura-text">{label}</span>
          {help && <p className="mt-0.5 text-xs text-veloura-muted/80">{help}</p>}
        </div>
        <input
          type="checkbox"
          className="h-5 w-5 accent-[#FFC0CB]"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          aria-label={label}
        />
      </div>
    );
  }

  const mode = String(s.embed_mode ?? 'embed');
  const rawMessage = String(s.message ?? '');
  const rawFooter = String(s.footer ?? '{boostcount} boosts ♡');
  const thumbMode = String(s.thumbnail_mode ?? 'member');
  const image = String(s.image_url ?? '') || null;
  const color = normalizeColor(String(s.color ?? '#FFC0CB'));

  const preview = buildPreview(rawMessage, rawFooter, mode, previewCtx);

  return (
    <>
      <ModuleCard
        icon="star"
        title="boosters"
        description="celebrate every boost — announcements, an optional booster role and milestone cards"
        enabled={Boolean(s.enabled)}
        onToggle={async (next) => {
          ms.update({ enabled: next });
          const ok = await ms.patch({ enabled: next });
          if (ok) toast.push(`booster announcements ${next ? 'enabled' : 'disabled'} ✦`, 'success');
        }}
      >
        <Tabs
          tabs={[
            { id: 'announcement', label: 'announcement', icon: 'heart' },
            { id: 'style', label: 'style', icon: 'wand' },
            { id: 'role', label: 'booster role', icon: 'users' },
            { id: 'milestones', label: 'milestones', icon: 'sparkles' },
          ]}
          active={tab}
          onChange={setTab}
        />

        {tab === 'announcement' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle icon="heart">when someone boosts</CardTitle>
              <div className="mt-4">
                <ChannelPicker
                  id="booster-channel"
                  label="announcement channel"
                  help="where booster announcements are posted"
                  value={s.channel_id as string | null}
                  onChange={(v) => ms.update({ channel_id: v })}
                />
                <MessageEditor
                  id="booster-message"
                  label="booster message"
                  help="tags: {user} {server} {boostcount} {boostlevel} — full list in /boosters show"
                  value={String(s.message ?? '')}
                  onChange={(v) => ms.update({ message: v })}
                  rows={10}
                />
              </div>
            </Card>

            <div className="lg:sticky lg:top-20 lg:self-start">
              <BoosterPreview
                mode={mode}
                content={preview.content}
                body={preview.body}
                footer={preview.footer}
                color={color}
                image={image}
                thumbMode={thumbMode}
                avatar={previewCtx.avatar}
                boostcount={previewCtx.boostcount}
              />
              <p className="mt-2 text-xs text-veloura-muted/80">
                live boost count on this server: <span className="text-veloura-pink">{previewCtx.boostcount}</span> — the preview renders with it
              </p>
              <button
                onClick={() => runAction('booster_test', 'test announcement queued — check the channel ✦')}
                disabled={testing || !s.channel_id}
                className="veloura-button-ghost mt-3 w-full !min-h-[40px] text-xs"
                title={s.channel_id ? 'send a real test announcement (nothing else changes)' : 'set a channel first'}
              >
                {testing ? 'sending…' : 'send test to discord'}
              </button>
              <p className="mt-1.5 text-[11px] text-veloura-muted/70">
                the test only renders and posts the announcement — no achievements, no role changes, no boost-count changes.
              </p>
            </div>
          </div>
        )}

        {tab === 'style' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle icon="wand">embed style</CardTitle>
              <div className="mt-4">
                <div className="mb-4">
                  <label htmlFor="booster-mode" className="veloura-label">
                    mode
                  </label>
                  <Select
                    id="booster-mode"
                    value={mode}
                    onChange={(e) => ms.update({ embed_mode: e.target.value })}
                  >
                    <option value="embed">embed — one elegant card</option>
                    <option value="text">text — plain message</option>
                    <option value="hybrid">hybrid — text + embed (split at ---)</option>
                  </Select>
                </div>
                <ColorPicker
                  label="accent color"
                  value={String(s.color ?? '#FFC0CB')}
                  onChange={(v) => ms.update({ color: v })}
                />
                <div className="mb-4">
                  <label htmlFor="booster-thumbnail" className="veloura-label">
                    thumbnail
                  </label>
                  <Select
                    id="booster-thumbnail"
                    value={thumbMode}
                    onChange={(e) => ms.update({ thumbnail_mode: e.target.value })}
                  >
                    <option value="member">booster avatar</option>
                    <option value="server">server icon</option>
                    <option value="none">none</option>
                  </Select>
                </div>
                <div className="mb-4">
                  <label htmlFor="booster-footer" className="veloura-label">
                    footer text
                  </label>
                  <TextInput
                    id="booster-footer"
                    placeholder="{boostcount} boosts ♡"
                    value={String(s.footer ?? '')}
                    onChange={(e) => ms.update({ footer: e.target.value })}
                  />
                </div>
                <div className="mb-4">
                  <label htmlFor="booster-image" className="veloura-label">
                    banner image url
                  </label>
                  <TextInput
                    id="booster-image"
                    placeholder="https://…"
                    value={String(s.image_url ?? '')}
                    onChange={(e) => ms.update({ image_url: e.target.value || null })}
                  />
                </div>
              </div>
            </Card>

            <div className="lg:sticky lg:top-20 lg:self-start">
              <BoosterPreview
                mode={mode}
                content={preview.content}
                body={preview.body}
                footer={preview.footer}
                color={color}
                image={image}
                thumbMode={thumbMode}
                avatar={previewCtx.avatar}
                boostcount={previewCtx.boostcount}
              />
            </div>
          </div>
        )}

        {tab === 'role' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle icon="users">booster role</CardTitle>
              <div className="mt-4">
                <RolePicker
                  id="booster-role"
                  label="role granted while boosting"
                  help="managed / integration roles (incl. Discord's native Server Booster role) are hidden — aurelia can only manage normal roles below her"
                  value={(s.booster_role_id as string | null) ?? null}
                  onChange={(v) => ms.update({ booster_role_id: v })}
                />
                {toggleRow(
                  'assign the role automatically on boost',
                  Boolean(s.auto_role),
                  (v) => ms.update({ auto_role: v }),
                  'requires the module to be enabled and a role selected',
                )}
                {toggleRow(
                  'remove the role when someone stops boosting',
                  Boolean(s.remove_role_on_unboost),
                  (v) => ms.update({ remove_role_on_unboost: v }),
                  'cleanup keeps running even when announcements are off',
                )}
              </div>
            </Card>
            <Card>
              <CardTitle icon="shield">how it behaves</CardTitle>
              <ul className="mt-4 space-y-2 text-sm text-veloura-muted">
                <li>・ the role is granted the moment a member starts boosting</li>
                <li>・ hierarchy-checked: aurelia never touches roles at/above her top role</li>
                <li>・ unboost is quiet — no public goodbye, the role is simply cleaned up</li>
                <li>・ earned achievements (supporter) are permanent and never removed</li>
              </ul>
            </Card>
          </div>
        )}

        {tab === 'milestones' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle icon="sparkles">boost milestones</CardTitle>
              <div className="mt-4">
                {toggleRow(
                  'announce milestone boost counts',
                  Boolean(s.milestone_enabled),
                  (v) => ms.update({ milestone_enabled: v }),
                  'posts once per threshold, ever — restart and boost-churn safe',
                )}
                <div className="mb-4">
                  <label htmlFor="booster-milestones" className="veloura-label">
                    thresholds (comma separated)
                  </label>
                  <TextInput
                    id="booster-milestones"
                    placeholder="2, 7, 14"
                    value={Array.isArray(s.milestone_counts) ? (s.milestone_counts as number[]).join(', ') : '2, 7, 14'}
                    onChange={(e) =>
                      ms.update({
                        milestone_counts: e.target.value
                          .split(',')
                          .map((p) => parseInt(p.trim(), 10))
                          .filter((n) => Number.isFinite(n) && n > 0),
                      })}
                  />
                  <p className="mt-1.5 text-xs text-veloura-muted/80">
                    defaults match Discord boost levels (2 · 7 · 14); natural counts like 5, 10, 20, 25, 50, 100 work too
                  </p>
                </div>
                <MessageEditor
                  id="booster-milestone-message"
                  label="milestone message"
                  help="tags: {server} {boostcount}"
                  value={String(s.milestone_message ?? '')}
                  onChange={(v) => ms.update({ milestone_message: v })}
                  rows={4}
                />
              </div>
            </Card>
            <Card>
              <CardTitle icon="scroll">already announced</CardTitle>
              <p className="mt-4 text-sm text-veloura-muted">
                the high-water mark is <span className="text-veloura-pink">{String(s.milestone_last ?? 0)}</span> — every
                threshold at or below it was already celebrated and will never repost, even after a restart or a boost dip.
              </p>
              <div className="mt-4">
                <button
                  onClick={() => {
                    if (!confirmingReset) {
                      setConfirmingReset(true);
                      setTimeout(() => setConfirmingReset(false), 4000);
                      return;
                    }
                    setConfirmingReset(false);
                    void runAction('booster_reset', 'booster settings reset to defaults ✦');
                  }}
                  disabled={testing}
                  className="veloura-button-ghost w-full !min-h-[40px] text-xs"
                  style={confirmingReset ? { borderColor: 'rgba(239,68,68,.6)', color: '#f87171' } : undefined}
                >
                  {confirmingReset ? 'click again to reset everything' : 'reset booster module'}
                </button>
                <p className="mt-1.5 text-[11px] text-veloura-muted/70">
                  wipes channel, message, style, role config and milestone state. discord roles and achievements are untouched.
                </p>
              </div>
            </Card>
          </div>
        )}
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('booster config saved ✦', 'success');
        }}
        onRevert={ms.revert}
      />
    </>
  );
}

function BoosterPreview({
  mode,
  content,
  body,
  footer,
  color,
  image,
  thumbMode,
  avatar,
  boostcount,
}: {
  mode: string;
  content: string | null;
  body: string;
  footer: string;
  color: string;
  image: string | null;
  thumbMode: string;
  avatar: string;
  boostcount: number;
}) {
  return (
    <div className="rounded-[12px] bg-[#313338] p-4 font-body">
      <p className="mb-1 flex items-center gap-2 text-xs font-semibold text-lavender-900">
        <span className="text-[#949BA4]">live preview</span>
        <span aria-hidden className="text-[#949BA4]">✦</span>
        <span className="text-[#949BA4] font-normal">boost announcement · {mode} mode</span>
      </p>

      <div className="mt-2 flex gap-3">
        <img src={avatar} alt="" width={40} height={40} className="mt-0.5 h-10 w-10 rounded-full" />
        <div className="min-w-0 flex-1">
          <p className="flex items-baseline gap-2">
            <span className="font-medium text-[#F2F3F5]">aurelia</span>
            <span className="rounded bg-[#5865F2] px-1 py-px text-[10px] font-semibold text-white">BOT</span>
            <span className="text-[11px] text-[#949BA4]">today at 4:20 PM</span>
          </p>

          {mode !== 'embed' && content !== null && (
            <p className="mt-0.5 whitespace-pre-wrap break-words text-[15px] leading-[1.375rem] text-[#DBDEE1]">
              {content || <span className="italic text-[#949BA4]">no message set…</span>}
            </p>
          )}

          {mode !== 'text' && (
            <div
              className="mt-1.5 max-w-[440px] overflow-hidden rounded-[4px]"
              style={{ background: '#2B2D31', borderLeft: `4px solid ${color}` }}
            >
              <div className="flex gap-4 p-3">
                <div className="min-w-0 flex-1">
                  <p className="whitespace-pre-wrap break-words text-sm leading-[1.125rem] text-[#DBDEE1]">
                    {body || <span className="italic text-[#949BA4]">no message set…</span>}
                  </p>
                  {image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={image} alt="booster banner" className="mt-3 max-h-56 w-full rounded-[4px] object-cover" />
                  )}
                  {footer && (
                    <p className="mt-2 flex items-center gap-1.5 text-xs text-[#949BA4]">
                      <img src={avatar} alt="" width={18} height={18} className="h-[18px] w-[18px] rounded-full" />
                      {footer.replace('{boostcount}', String(boostcount))}
                    </p>
                  )}
                </div>
                {thumbMode === 'member' && (
                  <img src={avatar} alt="" width={64} height={64} className="h-16 w-16 shrink-0 rounded-[4px]" />
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
