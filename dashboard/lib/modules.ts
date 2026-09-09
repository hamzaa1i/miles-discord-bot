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
    icon: 'heart',
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
    icon: 'star',
    settings: 'leveling',
    rich: true,
    fields: [],
  },
  qotd: {
    slug: 'qotd',
    route: 'qotd',
    title: 'qotd',
    short: 'a question every day',
    icon: 'helpCircle',
    settings: 'qotd',
    rich: true,
    fields: [],
  },
  moderation: {
    slug: 'moderation',
    route: 'moderation',
    title: 'moderation',
    short: 'warnings & thresholds',
    icon: 'swords',
    settings: 'moderation',
    rich: true,
    fields: [],
  },
  logging: {
    slug: 'logging',
    route: 'logging',
    title: 'logging',
    short: 'server event log',
    icon: 'scroll',
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
    icon: 'shield',
    settings: 'ai_automod',
    rich: true,
    fields: [],
  },
  ai: {
    slug: 'ai',
    route: 'ai',
    title: 'chat, memory & vibe',
    short: 'aurelia\'s mind',
    icon: 'moon',
    settings: 'proactive',
    fields: [
      { key: 'enabled', label: 'proactive chatter', type: 'boolean', help: 'let aurelia drift into conversation on her own' },
      { key: 'channel_ids', label: 'watched channels', type: 'channelMulti', help: 'channels proactive chatter may appear in' },
    ],
  },
  vibe: {
    slug: 'vibe',
    route: 'vibe',
    title: 'vibe & fortune',
    short: 'channel moods, daily cards, small decisions',
    icon: 'sparkles',
    fields: [],
  },
  recap: {
    slug: 'recap',
    route: 'recap',
    title: 'recap',
    short: 'what did i miss?',
    icon: 'scroll',
    fields: [],
  },
  warnings: {
    slug: 'warnings',
    route: 'warnings',
    title: 'warnings',
    short: 'the case history, searchable',
    icon: 'swords',
    fields: [],
  },
  onboarding: {
    slug: 'onboarding',
    route: 'onboarding',
    title: 'onboarding',
    short: 'a soft first message with role buttons',
    icon: 'sparkles',
    settings: 'onboarding',
    fields: [],
  },
  levelRewards: {
    slug: 'levelRewards',
    route: 'level-rewards',
    title: 'level rewards',
    short: 'roles earned at a level',
    icon: 'star',
    fields: [],
  },
  autorole: {
    slug: 'autorole',
    route: 'autorole',
    title: 'autorole',
    short: 'the role given on join',
    icon: 'sparkles',
    settings: 'autorole',
    fields: [],
  },
  selfRoles: {
    slug: 'selfRoles',
    route: 'self-roles',
    title: 'self-roles',
    short: 'members pick their own roles',
    icon: 'users',
    settings: 'self_roles',
    fields: [],
  },
  colorRoles: {
    slug: 'colorRoles',
    route: 'color-roles',
    title: 'color roles',
    short: 'personal colors from /color set',
    icon: 'zap',
    fields: [],
  },
  danger: {
    slug: 'danger',
    route: 'danger',
    title: 'danger zone',
    short: 'careful destructive actions & audit',
    icon: 'shieldAlert',
    fields: [],
  },
  polls: {
    slug: 'polls',
    route: 'polls',
    title: 'polls',
    short: 'reaction polls with /poll',
    icon: 'barChart',
    fields: [],
  },
  nick: {
    slug: 'nick',
    route: 'nick',
    title: 'nickname requests',
    short: 'gentle name changes',
    icon: 'pencil',
    settings: 'nick',
    rich: true,
    fields: [],
  },
  roles: {
    // legacy: the four roles tabs became dedicated routes (autorole,
    // self-roles, color-roles, onboarding). /roles itself now redirects
    // to /autorole — kept in the registry for old links only.
    slug: 'roles',
    route: 'autorole',
    title: 'roles',
    short: 'autorole · self roles · rewards · colors',
    icon: 'sparkles',
    fields: [],
  },
  confessions: {
    slug: 'confessions',
    route: 'confessions',
    title: 'confessions',
    short: 'anonymous whispers',
    icon: 'moon',
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
    icon: 'gift',
    rich: true,
    fields: [],
  },
  starboard: {
    slug: 'starboard',
    route: 'starboard',
    title: 'starboard',
    short: 'preserve the best moments',
    icon: 'star',
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
    icon: 'wand',
    rich: true,
    fields: [],
  },
  stats: {
    slug: 'stats',
    route: 'stats',
    title: 'statistics',
    short: 'the shape of your server',
    icon: 'barChart',
    fields: [],
  },
  achievements: {
    slug: 'achievements',
    route: 'achievements',
    title: 'achievements',
    short: 'badges & leaderboard',
    icon: 'trophy',
    fields: [],
  },
  fun: {
    slug: 'fun',
    route: 'fun',
    title: 'fun & games',
    short: 'vibe checks, fortunes and time capsules',
    icon: 'sparkles',
    fields: [],
  },
  reminders: {
    slug: 'reminders',
    route: 'reminders',
    title: 'reminders',
    short: 'your own /remind list — view & cancel',
    icon: 'timer',
    fields: [],
  },
  anniversary: {
    slug: 'anniversary',
    route: 'anniversary',
    title: 'anniversaries',
    short: 'celebrate the stayers',
    icon: 'calendarHeart',
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
    icon: 'cake',
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
    icon: 'bell',
    settings: 'bump_reminder',
    fields: [
      { key: 'channel_id', label: 'bump channel', type: 'channel', help: 'where disboard bump reminders are posted' },
    ],
  },
  boosters: {
    slug: 'boosters',
    route: 'boosters',
    title: 'boosters',
    short: 'celebrate every boost',
    icon: 'star',
    settings: 'boosters',
    rich: true,
    fields: [],
  },
  rules: {
    slug: 'rules',
    route: 'rules',
    title: 'rules',
    short: 'rules & agreement role',
    icon: 'scroll',
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
    icon: 'zap',
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
    icon: 'lock',
    fields: [],
  },
  overview: {
    slug: 'overview',
    route: '',
    title: 'overview',
    short: 'the heart of your server',
    icon: 'sparkles',
    fields: [],
  },
};

export const SIDEBAR: SidebarCategory[] = [
  {
    label: 'core',
    icon: 'sparkles',
    items: [
      { title: 'overview', route: '', icon: 'sparkles', slug: 'overview' },
      { title: 'statistics', route: 'stats', icon: 'barChart', slug: 'stats' },
    ],
  },
  {
    label: 'ai & engagement',
    icon: 'moon',
    items: [
      { title: 'chat & memory', route: 'ai', icon: 'moon', slug: 'ai' },
      { title: 'vibe & fortune', route: 'vibe', icon: 'sparkles', slug: 'vibe' },
      { title: 'qotd', route: 'qotd', icon: 'helpCircle', slug: 'qotd' },
      { title: 'recap', route: 'recap', icon: 'scroll', slug: 'recap' },
    ],
  },
  {
    label: 'moderation',
    icon: 'swords',
    items: [
      { title: 'ai automod', route: 'automod', icon: 'shield', slug: 'aiAutomod' },
      { title: 'warnings', route: 'warnings', icon: 'swords', slug: 'warnings' },
      { title: 'logging', route: 'logging', icon: 'scroll', slug: 'logging' },
    ],
  },
  {
    label: 'members',
    icon: 'heart',
    items: [
      { title: 'welcome & goodbye', route: 'welcome', icon: 'heart', slug: 'welcome' },
      { title: 'onboarding', route: 'onboarding', icon: 'sparkles', slug: 'onboarding' },
      { title: 'anniversaries', route: 'anniversary', icon: 'calendarHeart', slug: 'anniversary' },
      { title: 'nickname requests', route: 'nick', icon: 'pencil', slug: 'nick' },
    ],
  },
  {
    label: 'roles',
    icon: 'users',
    items: [
      { title: 'autorole', route: 'autorole', icon: 'sparkles', slug: 'autorole' },
      { title: 'self-roles', route: 'self-roles', icon: 'users', slug: 'selfRoles' },
      { title: 'level rewards', route: 'level-rewards', icon: 'star', slug: 'levelRewards' },
      { title: 'color roles', route: 'color-roles', icon: 'zap', slug: 'colorRoles' },
    ],
  },
  {
    label: 'community',
    icon: 'gift',
    items: [
      { title: 'leveling', route: 'leveling', icon: 'star', slug: 'leveling' },
      { title: 'achievements', route: 'achievements', icon: 'trophy', slug: 'achievements' },
      { title: 'confessions', route: 'confessions', icon: 'moon', slug: 'confessions' },
      { title: 'polls', route: 'polls', icon: 'barChart', slug: 'polls' },
      { title: 'giveaways', route: 'giveaways', icon: 'gift', slug: 'giveaways' },
      { title: 'starboard', route: 'starboard', icon: 'star', slug: 'starboard' },
      { title: 'boosters', route: 'boosters', icon: 'star', slug: 'boosters' },
      { title: 'custom commands', route: 'custom-commands', icon: 'wand', slug: 'customCommands' },
      { title: 'fun & games', route: 'fun', icon: 'sparkles', slug: 'fun' },
    ],
  },
  {
    label: 'utility',
    icon: 'zap',
    items: [
      { title: 'reminders', route: 'reminders', icon: 'timer', slug: 'reminders' },
      { title: 'birthdays', route: 'birthdays', icon: 'cake', slug: 'birthdays' },
      { title: 'bump reminder', route: 'bump-reminder', icon: 'bell', slug: 'bumpReminder' },
      { title: 'rules', route: 'rules', icon: 'scroll', slug: 'rules' },
      { title: 'prefix', route: 'prefix', icon: 'zap', slug: 'prefix' },
    ],
  },
  {
    label: 'server',
    icon: 'lock',
    items: [
      { title: 'privacy', route: 'privacy', icon: 'lock', slug: 'privacy' },
      { title: 'danger zone', route: 'danger', icon: 'shieldAlert', slug: 'danger' },
    ],
  },
];
