/**
 * lib/modules.ts — module registry + sidebar structure.
 *
 * Drives BOTH the sidebar (categories -> routes) and the generic
 * schema-driven SettingsForm used by thin module pages. Rich pages
 * (welcome, leveling, qotd, moderation, ...) build their own layouts
 * but reuse the same field primitives.
 */

export type FieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'boolean'
  | 'channel'
  | 'role'
  | 'color'
  | 'select'
  | 'channelMulti';

export interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  placeholder?: string;
  help?: string;
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  /** show under a section heading inside the form */
  section?: string;
  rows?: number;
}

export interface ModuleDef {
  slug: string;
  route: string;
  title: string;
  short: string;
  icon: string;
  /** settings endpoint slug (null = page is data/info only) */
  settings?: string;
  fields: FieldDef[];
  defaults?: Record<string, unknown>;
  rich?: boolean;
}

export interface SidebarCategory {
  label: string;
  icon: string;
  items: { title: string; route: string; icon: string; slug?: string }[];
}

export const MODULES: Record<string, ModuleDef> = {
  welcome: {
    slug: 'welcome',
    route: 'welcome',
    title: 'welcome & goodbye',
    short: 'greet every soul that drifts in',
    icon: '♡',
    settings: 'welcome',
    rich: true,
    fields: [],
    defaults: {
      enabled: false,
      channel_id: null,
      message: 'Welcome {user} to {server}! You are member #{membercount}.',
      embed_mode: 'embed',
      welcome_color: '#FFC0CB',
    },
  },
  leveling: {
    slug: 'leveling',
    route: 'leveling',
    title: 'leveling',
    short: 'xp, levels & role rewards',
    icon: '✩',
    settings: 'leveling',
    rich: true,
    fields: [],
  },
  qotd: {
    slug: 'qotd',
    route: 'qotd',
    title: 'qotd',
    short: 'a question every day',
    icon: '❓',
    settings: 'qotd',
    rich: true,
    fields: [],
  },
  moderation: {
    slug: 'moderation',
    route: 'moderation',
    title: 'moderation',
    short: 'warnings & thresholds',
    icon: '⚔',
    settings: 'moderation',
    rich: true,
    fields: [],
  },
  logging: {
    slug: 'logging',
    route: 'logging',
    title: 'logging',
    short: 'server event log',
    icon: '📜',
    settings: 'log',
    fields: [
      { key: 'enabled', label: 'enable logging', type: 'boolean' },
      { key: 'channel_id', label: 'log channel', type: 'channel' },
      { key: 'message_delete', label: 'message deletions', type: 'boolean', section: 'events' },
      { key: 'message_edit', label: 'message edits', type: 'boolean', section: 'events' },
      { key: 'member_join', label: 'member joins', type: 'boolean', section: 'events' },
      { key: 'member_leave', label: 'member leaves', type: 'boolean', section: 'events' },
      { key: 'member_ban', label: 'bans', type: 'boolean', section: 'events' },
      { key: 'member_unban', label: 'unbans', type: 'boolean', section: 'events' },
      { key: 'role_change', label: 'role changes', type: 'boolean', section: 'events' },
      { key: 'nickname_change', label: 'nickname changes', type: 'boolean', section: 'events' },
      { key: 'voice_join', label: 'voice joins', type: 'boolean', section: 'events' },
      { key: 'voice_leave', label: 'voice leaves', type: 'boolean', section: 'events' },
    ],
  },
  aiAutomod: {
    slug: 'aiAutomod',
    route: 'automod',
    title: 'ai automod',
    short: 'the watchful gaze',
    icon: '👁',
    settings: 'ai_automod',
    rich: true,
    fields: [],
  },
  ai: {
    slug: 'ai',
    route: 'ai',
    title: 'chat, memory & vibe',
    short: 'aurelia\'s mind',
    icon: '🌙',
    settings: 'proactive',
    fields: [
      { key: 'enabled', label: 'proactive chatter', type: 'boolean', help: 'let aurelia drift into conversation on her own' },
      { key: 'channel_ids', label: 'watched channels', type: 'channelMulti', help: 'channels proactive chatter may appear in' },
    ],
  },
  nick: {
    slug: 'nick',
    route: 'nick',
    title: 'nickname requests',
    short: 'gentle name changes',
    icon: '✎',
    settings: 'nick',
    rich: true,
    fields: [],
  },
  roles: {
    slug: 'roles',
    route: 'roles',
    title: 'roles',
    short: 'autorole · self roles · rewards · colors',
    icon: '✦',
    rich: true,
    fields: [],
  },
  confessions: {
    slug: 'confessions',
    route: 'confessions',
    title: 'confessions',
    short: 'anonymous whispers',
    icon: '🌙',
    settings: 'confess',
    fields: [
      { key: 'channel_id', label: 'confession channel', type: 'channel' },
    ],
  },
  giveaways: {
    slug: 'giveaways',
    route: 'giveaways',
    title: 'giveaways',
    short: 'gifts from the void',
    icon: '🎁',
    rich: true,
    fields: [],
  },
  starboard: {
    slug: 'starboard',
    route: 'starboard',
    title: 'starboard',
    short: 'preserve the best moments',
    icon: '⭐',
    settings: 'starboard',
    fields: [
      { key: 'enabled', label: 'enable starboard', type: 'boolean' },
      { key: 'channel_id', label: 'starboard channel', type: 'channel' },
      { key: 'emoji', label: 'star emoji', type: 'text', placeholder: '⭐' },
      { key: 'threshold', label: 'reaction threshold', type: 'number', min: 1, max: 50, help: 'reactions needed before a message is starred' },
    ],
  },
  customCommands: {
    slug: 'customCommands',
    route: 'custom-commands',
    title: 'custom commands',
    short: 'your own little spells',
    icon: '✧',
    rich: true,
    fields: [],
  },
  stats: {
    slug: 'stats',
    route: 'stats',
    title: 'statistics',
    short: 'the shape of your server',
    icon: '📈',
    fields: [],
  },
  achievements: {
    slug: 'achievements',
    route: 'achievements',
    title: 'achievements',
    short: 'badges & leaderboard',
    icon: '🏅',
    fields: [],
  },
  fun: {
    slug: 'fun',
    route: 'fun',
    title: 'fun & polls',
    short: 'vibe checks and fortunes',
    icon: '✧',
    fields: [],
  },
  anniversary: {
    slug: 'anniversary',
    route: 'anniversary',
    title: 'anniversaries',
    short: 'celebrate the stayers',
    icon: '🎂',
    settings: 'anniversary',
    fields: [
      { key: 'enabled', label: 'enable anniversaries', type: 'boolean' },
      { key: 'channel_id', label: 'announcement channel', type: 'channel' },
    ],
  },
  birthdays: {
    slug: 'birthdays',
    route: 'birthdays',
    title: 'birthdays',
    short: 'cakes on the right day',
    icon: '🍰',
    settings: 'birthdays',
    fields: [
      { key: 'channel_id', label: 'birthday channel', type: 'channel' },
    ],
  },
  bumpReminder: {
    slug: 'bumpReminder',
    route: 'bump-reminder',
    title: 'bump reminder',
    short: 'keep the server afloat',
    icon: '🫧',
    settings: 'bump_reminder',
    fields: [
      { key: 'channel_id', label: 'bump channel', type: 'channel', help: 'where disboard bump reminders are posted' },
    ],
  },
  rules: {
    slug: 'rules',
    route: 'rules',
    title: 'rules',
    short: 'rules & agreement role',
    icon: '📖',
    settings: 'rules',
    fields: [
      { key: 'rules', label: 'rules text', type: 'textarea', rows: 10, placeholder: '1. be soft\n2. be kind\n3. ...' },
      { key: 'agree_role_id', label: 'role granted on agree', type: 'role' },
      { key: 'announcement_channel_id', label: 'announcement channel', type: 'channel' },
    ],
  },
  prefix: {
    slug: 'prefix',
    route: 'prefix',
    title: 'prefix',
    short: 'the legacy prefix command',
    icon: '⌁',
    settings: 'prefix',
    fields: [
      { key: 'prefix', label: 'command prefix', type: 'text', placeholder: '!', help: 'for prefix (non-slash) commands' },
    ],
  },
  privacy: {
    slug: 'privacy',
    route: 'privacy',
    title: 'privacy & danger zone',
    short: 'data controls and audit',
    icon: '🔒',
    fields: [],
  },
  overview: {
    slug: 'overview',
    route: '',
    title: 'overview',
    short: 'the heart of your server',
    icon: '✦',
    fields: [],
  },
};

export const SIDEBAR: SidebarCategory[] = [
  {
    label: 'core',
    icon: '✦',
    items: [
      { title: 'overview', route: '', icon: '✦', slug: 'overview' },
      { title: 'statistics', route: 'stats', icon: '📈', slug: 'stats' },
    ],
  },
  {
    label: 'ai & engagement',
    icon: '🌙',
    items: [
      { title: 'chat & memory', route: 'ai', icon: '🌙', slug: 'ai' },
      { title: 'vibe & fortune', route: 'ai#vibe', icon: '✧', slug: 'ai' },
      { title: 'qotd', route: 'qotd', icon: '❓', slug: 'qotd' },
      { title: 'recap', route: 'ai#recap', icon: '📜', slug: 'ai' },
    ],
  },
  {
    label: 'moderation',
    icon: '⚔',
    items: [
      { title: 'automod', route: 'automod', icon: '👁', slug: 'aiAutomod' },
      { title: 'ai automod', route: 'automod', icon: '👁', slug: 'aiAutomod' },
      { title: 'warnings', route: 'moderation#warnings', icon: '⚔', slug: 'moderation' },
      { title: 'logging', route: 'logging', icon: '📜', slug: 'logging' },
    ],
  },
  {
    label: 'members',
    icon: '♡',
    items: [
      { title: 'welcome & goodbye', route: 'welcome', icon: '♡', slug: 'welcome' },
      { title: 'onboarding', route: 'roles#onboarding', icon: '✧', slug: 'roles' },
      { title: 'anniversaries', route: 'anniversary', icon: '🎂', slug: 'anniversary' },
      { title: 'nickname requests', route: 'nick', icon: '✎', slug: 'nick' },
    ],
  },
  {
    label: 'roles',
    icon: '✦',
    items: [
      { title: 'autorole', route: 'roles#autorole', icon: '✦', slug: 'roles' },
      { title: 'self-roles', route: 'roles#selfroles', icon: '✦', slug: 'roles' },
      { title: 'level rewards', route: 'leveling#rewards', icon: '✩', slug: 'leveling' },
      { title: 'color roles', route: 'roles#colors', icon: '🎨', slug: 'roles' },
    ],
  },
  {
    label: 'community',
    icon: '🫧',
    items: [
      { title: 'leveling', route: 'leveling', icon: '✩', slug: 'leveling' },
      { title: 'achievements', route: 'achievements', icon: '🏅', slug: 'achievements' },
      { title: 'confessions', route: 'confessions', icon: '🌙', slug: 'confessions' },
      { title: 'polls', route: 'fun', icon: '✧', slug: 'fun' },
      { title: 'giveaways', route: 'giveaways', icon: '🎁', slug: 'giveaways' },
      { title: 'starboard', route: 'starboard', icon: '⭐', slug: 'starboard' },
      { title: 'custom commands', route: 'custom-commands', icon: '✧', slug: 'customCommands' },
    ],
  },
  {
    label: 'utility',
    icon: '⌁',
    items: [
      { title: 'reminders', route: 'fun#reminders', icon: '⏰', slug: 'fun' },
      { title: 'birthdays', route: 'birthdays', icon: '🍰', slug: 'birthdays' },
      { title: 'bump reminder', route: 'bump-reminder', icon: '🫧', slug: 'bumpReminder' },
      { title: 'rules', route: 'rules', icon: '📖', slug: 'rules' },
      { title: 'prefix', route: 'prefix', icon: '⌁', slug: 'prefix' },
    ],
  },
  {
    label: 'server',
    icon: '🔒',
    items: [
      { title: 'privacy', route: 'privacy', icon: '🔒', slug: 'privacy' },
      { title: 'danger zone', route: 'privacy#danger', icon: '⚠', slug: 'privacy' },
    ],
  },
];
