'use client';

/**
 * Welcome module — the reference implementation for rich module pages.
 * Full config form + live Discord preview + test buttons.
 */

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { useModuleSettings } from '@/lib/useModuleSettings';
import { useAuth } from '@/lib/auth';
import { endpoints, ApiRequestError } from '@/lib/api';
import { ModuleCard } from '@/components/ModuleCard';
import { SaveBar } from '@/components/SaveBar';
import { ChannelPicker, RolePicker } from '@/components/ChannelPicker';
import { ColorPicker } from '@/components/ColorPicker';
import { MessageEditor } from '@/components/MessageEditor';
import { EmbedPreview } from '@/components/EmbedPreview';
import { Card, CardTitle, Select, TextInput, Tabs, LoadingCard, ErrorCard } from '@/components/ui/primitives';
import { useToast } from '@/components/ui/toast';
import { defaultAvatar } from '@/lib/discord';
import type { Settings } from '@/lib/types';

const DEFAULTS: Settings = {
  enabled: false,
  channel_id: null,
  message: 'Welcome {user} to {server}! You are member #{membercount}.',
  goodbye_enabled: false,
  goodbye_channel_id: null,
  goodbye_message: 'Goodbye {user}, we\u2019ll miss you.',
  embed_mode: 'embed',
  welcome_color: '#FFC0CB',
  welcome_image: null,
  welcome_title: '',
  welcome_thumbnail: 'avatar',
  welcome_footer: 'wrapped in veloura ✦',
  dm_message: '',
  autorole_id: null,
  welcome_reward: 500,
  welcomer_reward: 1000,
};

export default function WelcomePage() {
  const params = useParams<{ guildId: string }>();
  const gid = String(params.guildId);
  const { user } = useAuth();
  const toast = useToast();
  const ms = useModuleSettings(gid, 'welcome', DEFAULTS);
  const [tab, setTab] = useState('welcome');
  const [testing, setTesting] = useState(false);

  if (ms.loading) return <LoadingCard label="loading welcome config…" />;
  if (ms.error && !ms.settings) return <ErrorCard message={ms.error} />;
  if (!ms.settings) return null;

  const s = ms.settings as Record<string, Settings[keyof Settings]>;

  const previewCtx = {
    username: user?.display_name ?? 'newcomer',
    serverName: 'veloura lounge',
    membercount: 1337,
    avatar: user?.avatar ?? defaultAvatar(user?.id ?? '0'),
  };

  async function testWelcome(type: 'welcome' | 'goodbye') {
    setTesting(true);
    try {
      await endpoints.action(gid, 'welcome_test', { type });
      toast.push(`test ${type} queued — check the channel ✦`, 'success');
    } catch (e) {
      toast.push(e instanceof ApiRequestError ? e.message : 'test failed', 'error');
    } finally {
      setTesting(false);
    }
  }

  return (
    <>
      <ModuleCard
        icon="♡"
        title="welcome & goodbye"
        description="greet every soul that drifts in — and wish them well on the way out"
        enabled={Boolean(s.enabled)}
        onToggle={async (next) => {
          ms.update({ enabled: next });
          const ok = await ms.patch({ enabled: next });
          if (ok) toast.push(`welcome ${next ? 'enabled' : 'disabled'} ✦`, 'success');
        }}
      >
        <Tabs
          tabs={[
            { id: 'welcome', label: 'welcome', icon: '♡' },
            { id: 'goodbye', label: 'goodbye', icon: '✧' },
            { id: 'style', label: 'style & extras', icon: '✦' },
          ]}
          active={tab}
          onChange={setTab}
        />

        {tab === 'welcome' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle icon="♡">arrival</CardTitle>
              <div className="mt-4">
                <ChannelPicker
                  id="welcome-channel"
                  label="welcome channel"
                  value={s.channel_id as string | null}
                  onChange={(v) => ms.update({ channel_id: v })}
                />
                <MessageEditor
                  id="welcome-message"
                  label="welcome message"
                  help="use the template variables below — they fill in when the card posts"
                  value={String(s.message ?? '')}
                  onChange={(v) => ms.update({ message: v })}
                  rows={5}
                />
              </div>
            </Card>

            <div className="lg:sticky lg:top-20 lg:self-start">
              <EmbedPreview settings={ms.settings ?? {}} ctx={previewCtx} />
              <button
                onClick={() => testWelcome('welcome')}
                disabled={testing || !s.channel_id}
                className="veloura-button-ghost mt-3 w-full !min-h-[40px] text-xs"
                title={s.channel_id ? 'send a real test card' : 'set a channel first'}
              >
                {testing ? 'sending…' : '✧ send test to discord'}
              </button>
            </div>
          </div>
        )}

        {tab === 'goodbye' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardTitle icon="✧">departure</CardTitle>
              <div className="mt-4">
                <div className="mb-4 flex items-center justify-between gap-4 rounded-[12px] border border-veloura-border/60 bg-veloura-navy/50 px-4 py-3">
                  <span className="text-sm text-veloura-text">goodbye messages enabled</span>
                  <input
                    type="checkbox"
                    className="h-5 w-5 accent-[#FFC0CB]"
                    checked={Boolean(s.goodbye_enabled)}
                    onChange={(e) => ms.update({ goodbye_enabled: e.target.checked })}
                    aria-label="enable goodbye messages"
                  />
                </div>
                <ChannelPicker
                  id="goodbye-channel"
                  label="goodbye channel"
                  help="falls back to the welcome channel when unset"
                  value={(s.goodbye_channel_id as string | null) ?? null}
                  onChange={(v) => ms.update({ goodbye_channel_id: v })}
                />
                <MessageEditor
                  id="goodbye-message"
                  label="goodbye message"
                  value={String(s.goodbye_message ?? '')}
                  onChange={(v) => ms.update({ goodbye_message: v })}
                  rows={4}
                />
              </div>
            </Card>
            <div className="lg:sticky lg:top-20 lg:self-start">
              <EmbedPreview settings={ms.settings ?? {}} ctx={previewCtx} isGoodbye />
              <button
                onClick={() => testWelcome('goodbye')}
                disabled={testing || !(s.goodbye_channel_id ?? s.channel_id)}
                className="veloura-button-ghost mt-3 w-full !min-h-[40px] text-xs"
              >
                {testing ? 'sending…' : '✧ send test goodbye'}
              </button>
            </div>
          </div>
        )}

        {tab === 'style' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <Card>
                <CardTitle icon="✦">embed style</CardTitle>
                <div className="mt-4">
                  <div className="mb-4">
                    <label htmlFor="embed-mode" className="veloura-label">
                      mode
                    </label>
                    <Select
                      id="embed-mode"
                      value={String(s.embed_mode ?? 'embed')}
                      onChange={(e) => ms.update({ embed_mode: e.target.value })}
                    >
                      <option value="embed">embed — one elegant card</option>
                      <option value="text">text — plain message</option>
                      <option value="hybrid">hybrid — text + embed</option>
                    </Select>
                  </div>
                  <ColorPicker
                    label="accent color"
                    value={(s.welcome_color as string | null) ?? '#FFC0CB'}
                    onChange={(v) => ms.update({ welcome_color: v })}
                  />
                  <div className="mb-4">
                    <label htmlFor="welcome-title" className="veloura-label">
                      embed title
                    </label>
                    <TextInput
                      id="welcome-title"
                      placeholder="a new star drifts in ✦"
                      value={String(s.welcome_title ?? '')}
                      onChange={(e) => ms.update({ welcome_title: e.target.value })}
                    />
                  </div>
                  <div className="mb-4">
                    <label htmlFor="welcome-footer" className="veloura-label">
                      embed footer
                    </label>
                    <TextInput
                      id="welcome-footer"
                      placeholder="wrapped in veloura ✦"
                      value={String(s.welcome_footer ?? '')}
                      onChange={(e) => ms.update({ welcome_footer: e.target.value })}
                    />
                  </div>
                  <div className="mb-4">
                    <label htmlFor="welcome-thumbnail" className="veloura-label">
                      thumbnail
                    </label>
                    <Select
                      id="welcome-thumbnail"
                      value={String(s.welcome_thumbnail ?? 'avatar')}
                      onChange={(e) => ms.update({ welcome_thumbnail: e.target.value })}
                    >
                      <option value="avatar">member avatar</option>
                      <option value="none">none</option>
                    </Select>
                  </div>
                  <div className="mb-4">
                    <label htmlFor="welcome-image" className="veloura-label">
                      banner image url
                    </label>
                    <TextInput
                      id="welcome-image"
                      placeholder="https://…"
                      value={String(s.welcome_image ?? '')}
                      onChange={(e) => ms.update({ welcome_image: e.target.value || null })}
                    />
                  </div>
                </div>
              </Card>
            </div>

            <div className="space-y-4">
              <Card>
                <CardTitle icon="🎁">rewards & roles</CardTitle>
                <div className="mt-4">
                  <RolePicker
                    id="autorole"
                    label="autorole — granted on join"
                    value={(s.autorole_id as string | null) ?? null}
                    onChange={(v) => ms.update({ autorole_id: v })}
                  />
                  <div className="grid grid-cols-2 gap-4">
                    <div className="mb-4">
                      <label htmlFor="welcome-reward" className="veloura-label">
                        welcome xp
                      </label>
                      <TextInput
                        id="welcome-reward"
                        type="number"
                        min={0}
                        value={String(s.welcome_reward ?? 0)}
                        onChange={(e) => ms.update({ welcome_reward: Number(e.target.value) || 0 })}
                      />
                    </div>
                    <div className="mb-4">
                      <label htmlFor="welcomer-reward" className="veloura-label">
                        welcomer xp
                      </label>
                      <TextInput
                        id="welcomer-reward"
                        type="number"
                        min={0}
                        value={String(s.welcomer_reward ?? 0)}
                        onChange={(e) => ms.update({ welcomer_reward: Number(e.target.value) || 0 })}
                      />
                    </div>
                  </div>
                </div>
              </Card>
              <Card>
                <CardTitle icon="✉">welcome dm</CardTitle>
                <div className="mt-4">
                  <MessageEditor
                    label="dm text (sent after the card)"
                    help="leave empty to disable dms — members can opt out themselves"
                    value={String(s.dm_message ?? '')}
                    onChange={(v) => ms.update({ dm_message: v })}
                    rows={4}
                  />
                </div>
              </Card>
            </div>
          </div>
        )}
      </ModuleCard>

      <SaveBar
        dirty={ms.dirty}
        saving={ms.saving}
        error={ms.error}
        onSave={async () => {
          const ok = await ms.save();
          if (ok) toast.push('welcome config saved ✦', 'success');
        }}
        onRevert={ms.revert}
        onResetDefaults={async () => {
          const ok = await ms.resetDefaults();
          if (ok) toast.push('reset to veloura defaults', 'info');
        }}
      />
    </>
  );
}
