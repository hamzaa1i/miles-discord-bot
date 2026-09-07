/** Shared API response types (mirrors utils/dashboard_api.py shapes). */

export interface DashboardUser {
  id: string;
  username: string;
  global_name: string | null;
  display_name: string;
  avatar: string | null;
}

export interface ManageableGuild {
  id: string;
  name: string;
  icon: string | null;
  owner: boolean;
  member_count: number | null;
}

export interface UsageStats {
  commands_used_7d: number;
  active_users_7d: number;
  top_commands: { command: string; count: number }[];
}

export interface GuildOverview {
  id: string;
  name: string;
  icon: string | null;
  member_count: number | null;
  online_count: number | null;
  boost_count: number;
  bot_joined_at: string | null;
  active_features: Record<string, boolean>;
  stats: UsageStats;
}

export interface ChannelInfo {
  id: string;
  name: string;
  /** raw Discord channel type (0 text, 2 voice, 4 category, 5 announcement, 15 forum) */
  type: number;
  type_name: string;
  parent_id: string | null;
  parent_name: string | null;
  position: number;
  /** can the BOT see/send in this channel (backend-computed) */
  bot_can_view: boolean;
  bot_can_send: boolean;
}

export interface RoleInfo {
  id: string;
  name: string;
  /** integer color (0 = none) — display via intToHex */
  color: number;
  position: number;
  managed: boolean;
  hoisted: boolean;
  mentionable: boolean;
}

/** Legacy shape kept for older cached payloads: color may arrive as hex. */
export function roleColorHex(color: number | string | null | undefined): string | null {
  if (color === null || color === undefined || color === 0 || color === '') return null;
  if (typeof color === 'string') return color.startsWith('#') ? color : `#${color}`;
  return `#${color.toString(16).padStart(6, '0')}`;
}

export interface GuildResources {
  channels: ChannelInfo[];
  roles: RoleInfo[];
  member_count: number | null;
  boost_count: number;
  bot_permissions: {
    manage_roles: boolean;
    manage_channels: boolean;
    moderate_members: boolean;
    send_messages: boolean;
    embed_links: boolean;
  };
}

export type Settings = Record<string, unknown>;

export interface AuditEntry {
  id?: number;
  user_id: string;
  guild_id: string;
  action: string;
  details: string | null;
  ip_address?: string | null;
  timestamp: string;
}

export interface CustomCommand {
  trigger: string;
  response: string;
  uses?: number;
  created_by?: string;
}

export interface Giveaway {
  id: string;
  guild_id: string;
  channel_id: string;
  prize: string;
  ends_at: number;
  winners_count: number;
  host_name?: string;
  ended: boolean;
  entries: string[];
  winner_ids: string[];
  created_at: string;
}

export interface Warning {
  id?: number;
  case_id?: number;
  guild_id: string;
  user_id: string;
  type: string;
  reason: string | null;
  mod_name: string | null;
  mod_id: string | null;
  timestamp: string | null;
}

export interface QotdQueueRow {
  id?: number | string;
  question: string;
  added_by?: string;
  used: boolean;
  added_at?: string;
}

export interface StatsData {
  series: { date: string; commands: number; active_users: number }[];
  top_commands: { command: string; count: number }[];
  leveling_leaderboard: {
    user_id: string;
    display_name?: string;
    xp?: number;
    level?: number;
    messages?: number;
  }[];
  total_30d: number;
}

export interface LeaderboardRow {
  user_id: string;
  display_name: string;
  achievements: number;
  latest: string;
}

export interface LevelReward {
  level: number;
  role_id: string;
  role_name: string | null;
  role_color: string | null;
}

export interface NickRequest {
  id: number | string;
  user_id: string;
  current_nick: string;
  requested_nick: string;
  status: string;
  reason?: string | null;
  created_at: string;
}

export interface ColorRoleRow {
  user_id: string;
  display_name: string;
  role_id: string;
  hex_color: string;
  last_changed: string | null;
}

export interface ApiError {
  error: string;
  allowed?: string[];
  retry?: boolean;
}

export interface ReminderRow {
  id: string;
  text: string;
  end_time: number | null;
  repeat: string;
  channel_id?: string;
  created_at?: string | null;
}

export interface PollRow {
  message_id: string;
  channel_id: string;
  question: string;
  options: string[];
  author_name: string;
  end_time: number | null;
}

export interface AchievementBadge {
  key: string;
  name: string;
  description: string;
  emoji: string;
  rarity: 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary' | string;
  unlocked_by: number;
}
