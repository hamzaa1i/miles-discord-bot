'use client';

/**
 * lib/api.ts — typed client for the Flask dashboard API.
 *
 * Every call goes through the Next.js proxy route
 * (app/api/proxy/[...path]/route.ts) which:
 *   1. reads the Discord OAuth token from the httpOnly cookie
 *      (the token is NEVER exposed to client-side JavaScript),
 *   2. forwards the Authorization + X-CSRF-Token headers to the
 *      Flask backend on Render,
 *   3. relays the JSON response + status code.
 *
 * Mutations (PATCH/POST/DELETE) fetch a CSRF token first — the Flask
 * API binds each token to the bearer and requires the X-CSRF-Token
 * header on every non-GET request.
 */

const BASE = '/api/proxy/dashboard';

export class ApiRequestError extends Error {
  status: number;
  body: Record<string, unknown> | null;

  constructor(status: number, message: string, body: Record<string, unknown> | null) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

let csrfToken: string | null = null;

async function ensureCsrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  const res = await fetch(`${BASE}/csrf`, { cache: 'no-store' });
  if (!res.ok) throw new ApiRequestError(res.status, 'could not get csrf token', null);
  const body = (await res.json()) as { csrf_token: string };
  csrfToken = body.csrf_token;
  return csrfToken;
}

/** Reset the cached CSRF token (e.g. after a 403). */
export function resetCsrf() {
  csrfToken = null;
}

async function request<T>(
  method: 'GET' | 'PATCH' | 'POST' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') {
    try {
      headers['X-CSRF-Token'] = await ensureCsrf();
    } catch {
      // let the request go through; the backend will reject with 403
      // and the UI will surface a clear error
    }
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  });

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const errBody = (data ?? {}) as Record<string, unknown>;
    const msg =
      typeof errBody.error === 'string' ? errBody.error : `request failed (${res.status})`;
    if (res.status === 403 && /csrf/i.test(msg)) resetCsrf();
    throw new ApiRequestError(res.status, msg, errBody);
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string) => request<T>('GET', path),
  patch: <T,>(path: string, body: unknown) => request<T>('PATCH', path, body),
  post: <T,>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  delete: <T,>(path: string) => request<T>('DELETE', path),
};

/* ── Endpoint helpers ──────────────────────────────────────────── */

import type {
  AchievementBadge,
  AuditEntry,
  CustomCommand,
  DashboardUser,
  Giveaway,
  GuildOverview,
  GuildResources,
  LeaderboardRow,
  LevelReward,
  ManageableGuild,
  NickRequest,
  QotdQueueRow,
  ReminderRow,
  Settings,
  StatsData,
  Warning,
  ColorRoleRow,
} from './types';

/** Statuses worth one automatic retry after a short delay. */
export function retryableStatus(status: number): boolean {
  return status === 429 || status === 502 || status === 503 || status === 504;
}

/** fetch a GET with one retry on 429/5xx (transient backend/network). */
export async function getWithRetry<T>(
  path: string,
  { retries = 2, delayMs = 1000 }: { retries?: number; delayMs?: number } = {},
): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await api.get<T>(path);
    } catch (e) {
      lastErr = e;
      const retryable = e instanceof ApiRequestError && retryableStatus(e.status);
      const retryableNetwork = !(e instanceof ApiRequestError);
      if ((retryable || retryableNetwork) && attempt < retries) {
        await new Promise((r) => setTimeout(r, delayMs * (attempt + 1)));
        continue;
      }
      throw e;
    }
  }
  throw lastErr;
}

export interface UserResponse {
  user: DashboardUser;
  guilds: ManageableGuild[];
}

export interface SettingsResponse {
  module: string;
  settings: Settings;
  note?: string;
  data_endpoint?: string;
}

export const endpoints = {
  user: () => api.get<UserResponse>('/user'),

  overview: (gid: string) => api.get<GuildOverview>(`/guild/${gid}/overview`),

  resources: (gid: string) => api.get<GuildResources>(`/guild/${gid}/resources`),

  discordChannels: (gid: string) =>
    api.get<{ channels: GuildResources['channels'] }>(`/guild/${gid}/discord/channels`),

  discordRoles: (gid: string) =>
    api.get<{ roles: GuildResources['roles'] }>(`/guild/${gid}/discord/roles`),

  settings: (gid: string, module: string) =>
    api.get<SettingsResponse>(`/guild/${gid}/settings/${module}`),

  patchSettings: (gid: string, module: string, patch: Settings) =>
    api.patch<SettingsResponse>(`/guild/${gid}/settings/${module}`, patch),

  action: (gid: string, action: string, params: Record<string, unknown> = {}) =>
    api.post<{ queued: boolean; action: string }>(`/guild/${gid}/action/${action}`, params),

  moduleData: (gid: string, module: string) =>
    api.get<Record<string, unknown>>(`/guild/${gid}/module/${module}/data`),

  deleteData: (gid: string, type: string, id: string) =>
    api.delete<{ deleted: boolean }>(`/guild/${gid}/data/${type}/${id}`),

  audit: (gid: string) => api.get<{ entries: AuditEntry[] }>(`/guild/${gid}/audit`),

  warnings: (gid: string, page = 1, perPage = 20, user?: string) =>
    api.get<{ warnings: Warning[]; total: number; page: number; per_page: number }>(
      `/guild/${gid}/module/warnings/data?page=${page}&per_page=${perPage}${user ? `&user=${user}` : ''}`,
    ),

  customCommands: (gid: string) =>
    api.get<{ custom_commands: CustomCommand[] }>(`/guild/${gid}/module/custom_commands/data`),

  giveaways: (gid: string) =>
    api.get<{ active: Giveaway[]; past: Giveaway[] }>(`/guild/${gid}/module/giveaways/data`),

  qotdQueue: (gid: string) =>
    api.get<{ queue: QotdQueueRow[] }>(`/guild/${gid}/module/qotd/data`),

  stats: (gid: string) => api.get<StatsData>(`/guild/${gid}/module/stats/data`),

  achievements: (gid: string) =>
    api.get<{ leaderboard: LeaderboardRow[]; catalog: AchievementBadge[] }>(
      `/guild/${gid}/module/achievements/data`),

  levelRewards: (gid: string) =>
    api.get<{ rewards: LevelReward[] }>(`/guild/${gid}/module/level_rewards/data`),

  nickPending: (gid: string) =>
    api.get<{ pending: NickRequest[] }>(`/guild/${gid}/module/nick/data`),

  colorRoles: (gid: string) =>
    api.get<{ color_roles: ColorRoleRow[] }>(`/guild/${gid}/module/colors/data`),

  reminders: () => api.get<{ reminders: ReminderRow[] }>('/reminders'),

  deleteReminder: (id: string) =>
    api.delete<{ deleted: boolean }>(`/reminders/${encodeURIComponent(id)}`),
};
