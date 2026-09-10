/**
 * tests/boosters-page.test.tsx — runtime regression guard for the
 * Boosters page crash (minified React error #310).
 *
 * Phase O shipped a `useMemo` BELOW the loading/error early-returns:
 * the loading render called 8 hooks, the loaded render called 9, and
 * React threw "Rendered more hooks than during the previous render"
 * the moment module settings resolved — the whole page crashed in
 * production. `npm run build` passed, so a build-only check can never
 * catch this class of bug.
 *
 * These tests perform the REAL render transitions in jsdom against the
 * real page component with the network layer mocked at `fetch` level:
 *
 *   1. loading → settings loaded → full page (the exact crash path)
 *   2. cold mount at a direct /servers/[guildId]/boosters URL
 *   3. loading → settings error → error card
 *   4. tab interactions (re-renders must stay hook-stable)
 *
 * If a hook ever appears after a conditional return again, test 1
 * fails with "Rendered more hooks than during the previous render".
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { ToastProvider } from '@/components/ui/toast';
import { AuthProvider } from '@/lib/auth';
import { GuildProvider } from '@/lib/guild';
import BoostersPage from '@/app/servers/[guildId]/boosters/page';
import type {
  ChannelInfo,
  DashboardUser,
  GuildOverview,
  GuildResources,
  ManageableGuild,
  RoleInfo,
  UsageStats,
} from '@/lib/types';

/* ── route simulation (next/navigation is mocked) ──────────────── */

const route = vi.hoisted(() => ({ guildId: '' }));
vi.mock('next/navigation', () => ({
  useParams: () => ({ guildId: route.guildId }),
}));

/* ── fixtures ──────────────────────────────────────────────────── */

const GID = '111222333444555666';
const ALT_GID = '999888777666555444'; // fresh guild = no sessionStorage cache (cold direct load)

const user: DashboardUser = {
  id: '698142490775257119',
  username: 'volc',
  global_name: 'volc',
  display_name: 'volc',
  avatar: null,
};

const guilds: ManageableGuild[] = [
  { id: GID, name: 'veloura lounge', icon: null, owner: false, member_count: 42 },
];

const stats: UsageStats = {
  commands_used_7d: 120,
  active_users_7d: 12,
  top_commands: [{ command: '/hug', count: 40 }],
};

function overviewFor(gid: string): GuildOverview {
  return {
    id: gid,
    name: 'veloura lounge',
    icon: null,
    member_count: 42,
    online_count: 7,
    boost_count: 2,
    bot_joined_at: '2024-01-15T00:00:00Z',
    active_features: { boosters: true },
    stats,
  };
}

const channel: ChannelInfo = {
  id: '333444555666777888',
  name: 'announcements',
  type: 0,
  type_name: 'text',
  parent_id: null,
  parent_name: null,
  position: 0,
  bot_can_view: true,
  bot_can_send: true,
};

const role: RoleInfo = {
  id: '444555666777888999',
  name: 'booster',
  color: 16711935,
  position: 2,
  managed: false,
  hoisted: true,
  mentionable: true,
};

function resourcesFor(gid: string): GuildResources {
  return {
    channels: [channel],
    roles: [role],
    member_count: 42,
    boost_count: 2,
    bot_permissions: {
      manage_roles: true,
      manage_channels: true,
      moderate_members: true,
      send_messages: true,
      embed_links: true,
    },
  };
}

const BOOSTER_SETTINGS = {
  enabled: true,
  channel_id: '333444555666777888',
  message: 'thank you {user} for boosting **{server}**! now {boostcount} boosts',
  embed_mode: 'embed',
  color: '#FFC0CB',
  image_url: null,
  thumbnail_mode: 'member',
  footer: '{boostcount} boosts ♡',
  booster_role_id: null,
  auto_role: false,
  remove_role_on_unboost: true,
  milestone_enabled: true,
  milestone_message: '{server} reached {boostcount} boosts',
  milestone_counts: [2, 7, 14],
  milestone_last: 0,
};

/* ── fetch mock (response objects shaped like api.ts expects) ──── */

function jsonRes(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

/**
 * Gate that keeps the settings GET pending until releaseSettings() is
 * called — this is what lets a test hold the page in its LOADING
 * render and then flip it to LOADED, reproducing the production crash
 * transition on demand.
 */
let releaseSettings: ((s: Record<string, unknown>) => void) | null = null;
let settingsGate: Promise<Record<string, unknown>> | null = null;

function gateSettings(): void {
  settingsGate = new Promise<Record<string, unknown>>((res) => {
    releaseSettings = res;
  });
}

function stubApi(gid: string, opts: { settingsStatus?: number; deferSettings?: boolean } = {}): void {
  const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input);
    if (url.endsWith('/api/proxy/dashboard/csrf')) {
      return jsonRes({ csrf_token: 'test-csrf' });
    }
    if (url.endsWith('/api/proxy/dashboard/user')) {
      return jsonRes({ user, guilds });
    }
    if (url.includes(`/guild/${gid}/settings/boosters`)) {
      if (opts.deferSettings && settingsGate) {
        // json() resolves only when the test releases the gate
        return jsonRes(await settingsGate);
      }
      if (opts.settingsStatus && opts.settingsStatus >= 400) {
        return jsonRes({ error: 'boom' }, opts.settingsStatus);
      }
      return jsonRes({ module: 'boosters', settings: BOOSTER_SETTINGS });
    }
    if (url.includes(`/guild/${gid}/overview`)) {
      return jsonRes(overviewFor(gid));
    }
    if (url.includes(`/guild/${gid}/resources`)) {
      return jsonRes(resourcesFor(gid));
    }
    if (url.includes(`/guild/${gid}/audit`)) {
      return jsonRes({ entries: [] });
    }
    if (url.includes('/action/')) {
      return jsonRes({ queued: true, action: 'booster_test' });
    }
    return jsonRes({ error: `unexpected fetch: ${url}` }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
}

/* ── harness ───────────────────────────────────────────────────── */

function renderBoostersPage(gid: string) {
  route.guildId = gid;
  return render(
    <ToastProvider>
      <AuthProvider>
        <GuildProvider guildId={gid}>
          <BoostersPage />
        </GuildProvider>
      </AuthProvider>
    </ToastProvider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  releaseSettings = null;
  settingsGate = null;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

/* ── the tests ─────────────────────────────────────────────────── */

describe('boosters page — hook-order regression (React #310)', () => {
  it('renders loading, then the loaded page, without a hook-order exception', async () => {
    gateSettings();
    stubApi(GID, { deferSettings: true });

    renderBoostersPage(GID);

    // 1. the LOADING render — LoadingCard, no settings yet
    expect(screen.getByText(/loading booster config/i)).toBeTruthy();

    // 2. release the settings gate → the LOADED render happens here.
    //    With the old implementation (useMemo below the early returns)
    //    this re-render threw "Rendered more hooks than during the
    //    previous render" and this line fails the test.
    releaseSettings?.({ module: 'boosters', settings: BOOSTER_SETTINGS });

    // 3. the full page is alive — module heading + live preview
    const heading = await screen.findByRole('heading', { name: 'boosters' });
    expect(heading).toBeTruthy();

    // the preview substituted {server}/{user}/{boostcount} with the
    // real guild context (no 'your server' placeholder once overview
    // is available)
    await waitFor(() => {
      expect(screen.getByText(/veloura lounge/i)).toBeTruthy();
    });

    // the boost-count line is split across a <span> — assert on the
    // paragraph's full text content
    const liveCount = screen.getByText(/live boost count on this server/i);
    expect(liveCount.textContent).toMatch(/live boost count on this server: 2/);

    // no React exception was thrown during any render of this test
  });

  it('cold direct URL load: mounts fresh and renders the announcement', async () => {
    // a fresh guild id ⇒ no sessionStorage resources cache, exactly
    // like opening /servers/<gid>/boosters directly in a browser
    window.history.pushState({}, '', `/servers/${ALT_GID}/boosters`);
    stubApi(ALT_GID);

    renderBoostersPage(ALT_GID);

    const heading = await screen.findByRole('heading', { name: 'boosters' });
    expect(heading).toBeTruthy();
    expect(screen.getByRole('button', { name: /send test to discord/i })).toBeTruthy();
  });

  it('settings error shows the error card without crashing', async () => {
    stubApi(GID, { settingsStatus: 500 });

    renderBoostersPage(GID);

    // loading first, then the error card — both are early-return
    // renders; neither may change the hook count. The card shows the
    // API error message ('boom' comes from the mocked 500 body).
    await waitFor(() => {
      expect(screen.getByText('boom')).toBeTruthy();
    });
  });

  it('tab interactions re-render the loaded page without hook errors', async () => {
    stubApi(GID);

    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });

    // announcement tab is the default
    expect(screen.getByText(/announcement channel/i)).toBeTruthy();

    // Tabs render as role="tab" buttons — switching them re-renders
    // the page with different content while every hook stays put
    screen.getByRole('tab', { name: /style/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/embed style/i)).toBeTruthy();
    });

    // booster role tab
    screen.getByRole('tab', { name: /booster role/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/role granted while boosting/i)).toBeTruthy();
    });

    // milestones tab
    screen.getByRole('tab', { name: /milestones/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/boost milestones/i)).toBeTruthy();
    });

    // back to announcement — full cycle of re-renders stayed hook-stable
    screen.getByRole('tab', { name: /announcement/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/announcement channel/i)).toBeTruthy();
    });
  });
});

/* ══════════════════════════════════════════════════════════════════
 * PHASE O.2 — save flow & useModuleSettings state preservation
 *
 * Production exposed two related bugs this suite pins down:
 *
 *  1. BACKEND: Save Changes 500'd with a raw TypeError (the enum
 *     normalization bug — regression-tested server-side in
 *     scripts/test_dashboard_api.py; here we assert the sanitized
 *     client surface: no Python internals ever reach the UI).
 *
 *  2. FRONTEND: useModuleSettings.patch() REPLACED local settings with
 *     the PATCH response, so the enable toggle (an immediate partial
 *     PATCH of {enabled}) silently discarded unsaved edits — the
 *     selected channel, drafted message, picked color. The user had to
 *     know a magic ordering (enable FIRST, then edit). The hook now
 *     preserves dirty fields not covered by the patch.
 *
 * The fetch mock below models the REAL backend contract: PATCH is
 * partial, the response carries the full merged server state, and the
 * server may normalize fields (milestone_last pinning on enable).
 * ══════════════════════════════════════════════════════════════════ */

import { fireEvent } from '@testing-library/react';

const BOOSTING_CHANNEL: ChannelInfo = {
  id: '987654321098765432',
  name: 'boosting',
  type: 0,
  type_name: 'text',
  parent_id: null,
  parent_name: null,
  position: 1,
  bot_can_view: true,
  bot_can_send: true,
};

const DEFAULT_MESSAGE_TEXT =
  'thank you {user} for boosting **{server}**! now {boostcount} boosts';

/** server-side store — the source of truth the mock API serves */
let serverStore: Record<string, unknown>;
let patchCalls: Array<Record<string, unknown>>;

function stubApiWithStore(gid: string, opts: { patchStatus?: number } = {}): void {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/api/proxy/dashboard/csrf')) {
      return jsonRes({ csrf_token: 'test-csrf' });
    }
    if (url.endsWith('/api/proxy/dashboard/user')) {
      return jsonRes({ user, guilds });
    }
    if (url.includes(`/guild/${gid}/settings/boosters`)) {
      if (method === 'PATCH') {
        const body = JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>;
        if (opts.patchStatus && opts.patchStatus >= 400) {
          return jsonRes(
            {
              error:
                "couldn't complete that — please refresh and try again (ref ab12cd34)",
            },
            opts.patchStatus,
          );
        }
        patchCalls.push(body);
        // real backend semantics: merge into server state …
        Object.assign(serverStore, body);
        // … and normalize: enabling pins the milestone high-water mark
        // to the current boost count (resources say 2)
        if (body.enabled === true && serverStore.milestone_enabled === true) {
          serverStore.milestone_last = 2;
        }
        return jsonRes({ module: 'boosters', settings: { ...serverStore } });
      }
      return jsonRes({ module: 'boosters', settings: { ...serverStore } });
    }
    if (url.includes(`/guild/${gid}/overview`)) {
      return jsonRes(overviewFor(gid));
    }
    if (url.includes(`/guild/${gid}/resources`)) {
      return jsonRes({ ...resourcesFor(gid), channels: [channel, BOOSTING_CHANNEL] });
    }
    if (url.includes(`/guild/${gid}/audit`)) {
      return jsonRes({ entries: [] });
    }
    if (url.includes('/action/')) {
      return jsonRes({ queued: true, action: 'booster_reset' });
    }
    return jsonRes({ error: `unexpected fetch: ${method} ${url}` }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
}

const INITIAL_STORE = {
  enabled: false,
  channel_id: null as string | null,
  message: DEFAULT_MESSAGE_TEXT,
  embed_mode: 'embed',
  color: '#FFC0CB',
  image_url: null,
  thumbnail_mode: 'member',
  footer: '{boostcount} boosts ♡',
  booster_role_id: null as string | null,
  auto_role: false,
  remove_role_on_unboost: true,
  milestone_enabled: true,
  milestone_message: '{server} reached {boostcount} boosts',
  milestone_counts: [2, 7, 14],
  milestone_last: 0,
};

function freshStore(): Record<string, unknown> {
  return JSON.parse(JSON.stringify(INITIAL_STORE)) as Record<string, unknown>;
}

beforeEach(() => {
  serverStore = freshStore();
  patchCalls = [];
});

/** helpers over the real page DOM (native select/textarea/input) */
function channelSelect(): HTMLSelectElement {
  return screen.getByLabelText('announcement channel') as HTMLSelectElement;
}
function messageArea(): HTMLTextAreaElement {
  return screen.getByLabelText('booster message') as HTMLTextAreaElement;
}
function colorInput(): HTMLInputElement {
  return screen.getByLabelText('hex color value') as HTMLInputElement;
}
function enableSwitch(): HTMLElement {
  return screen.getByRole('switch', { name: 'toggle boosters' });
}
function saveButton(): HTMLElement {
  return screen.getByRole('button', { name: /save changes/i });
}

describe('boosters save flow — state preservation (PHASE O.2)', () => {
  it('select channel → Save Changes → PATCH 200 → reload persists', async () => {
    stubApiWithStore(GID);
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });

    // the exact production flow: pick a channel, hit Save Changes
    fireEvent.change(channelSelect(), { target: { value: BOOSTING_CHANNEL.id } });
    expect(channelSelect().value).toBe(BOOSTING_CHANNEL.id);
    expect(screen.getByText('unsaved changes')).toBeTruthy();

    fireEvent.click(saveButton());
    await waitFor(() => {
      expect(patchCalls.length).toBe(1);
    });
    expect(patchCalls[0]).toEqual({ channel_id: BOOSTING_CHANNEL.id });

    // hard reload: unmount + fresh mount against the same server store
    cleanup();
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });
    await waitFor(() => {
      expect(channelSelect().value).toBe(BOOSTING_CHANNEL.id);
    });
  });

  it('select channel BEFORE enabling → toggle → channel survives → save → both persist', async () => {
    stubApiWithStore(GID);
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });

    // 1. unsaved local channel selection
    fireEvent.change(channelSelect(), { target: { value: BOOSTING_CHANNEL.id } });

    // 2. immediate partial PATCH of an unrelated field (the enable
    //    toggle). OLD hook: response REPLACED settings → the channel
    //    selection was silently wiped. NEW hook: it survives.
    fireEvent.click(enableSwitch());
    await waitFor(() => {
      expect(patchCalls.length).toBe(1);
    });
    expect(patchCalls[0]).toEqual({ enabled: true });

    await waitFor(() => {
      // THE regression assertion: still selected after the toggle's
      // PATCH response landed
      expect(channelSelect().value).toBe(BOOSTING_CHANNEL.id);
    });
    // server-authoritative for the patched field: milestone_last pinned
    screen.getByRole('tab', { name: /milestones/i }).click();
    await waitFor(() => {
      expect(
        screen.getByText(/the high-water mark is/i).textContent,
      ).toMatch(/2/);
    });
    screen.getByRole('tab', { name: /announcement/i }).click();
    // …and the channel edit is still dirty, waiting to be saved
    expect(screen.getByText('unsaved changes')).toBeTruthy();

    // 3. save commits the remaining dirty field
    fireEvent.click(saveButton());
    await waitFor(() => {
      expect(patchCalls.length).toBe(2);
    });
    expect(patchCalls[1]).toEqual({ channel_id: BOOSTING_CHANNEL.id });

    // 4. hard reload: channel AND enabled state persist
    cleanup();
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });
    await waitFor(() => {
      expect(channelSelect().value).toBe(BOOSTING_CHANNEL.id);
    });
    expect(enableSwitch().getAttribute('aria-checked')).toBe('true');
  });

  it('edit message + color + channel, THEN enable — every edit survives, saves and persists', async () => {
    stubApiWithStore(GID);
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });

    const editedMessage = 'welcome to the stars, {user} ♡';
    const editedColor = '#A8E6CF';

    fireEvent.change(channelSelect(), { target: { value: BOOSTING_CHANNEL.id } });
    fireEvent.change(messageArea(), { target: { value: editedMessage } });
    // the color picker lives on the style tab — switch there, edit,
    // then return (tab switches must never drop the unsaved edits)
    screen.getByRole('tab', { name: /style/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/embed style/i)).toBeTruthy();
    });
    fireEvent.change(colorInput(), { target: { value: editedColor } });
    screen.getByRole('tab', { name: /announcement/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/announcement channel/i)).toBeTruthy();
    });

    fireEvent.click(enableSwitch());
    await waitFor(() => {
      expect(patchCalls.length).toBe(1);
    });
    expect(patchCalls[0]).toEqual({ enabled: true });

    // ALL unsaved edits survive the enable PATCH (channel/message on
    // the announcement tab, color on the style tab)
    await waitFor(() => {
      expect(channelSelect().value).toBe(BOOSTING_CHANNEL.id);
      expect(messageArea().value).toBe(editedMessage);
    });
    screen.getByRole('tab', { name: /style/i }).click();
    await waitFor(() => {
      expect(colorInput().value).toBe(editedColor);
    });
    screen.getByRole('tab', { name: /announcement/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/announcement channel/i)).toBeTruthy();
    });

    // save commits the three dirty fields in ONE patch
    fireEvent.click(saveButton());
    await waitFor(() => {
      expect(patchCalls.length).toBe(2);
    });
    expect(patchCalls[1]).toEqual({
      channel_id: BOOSTING_CHANNEL.id,
      message: editedMessage,
      color: editedColor,
    });

    // hard reload: everything persisted (channel/message on the
    // announcement tab, color on the style tab)
    cleanup();
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });
    await waitFor(() => {
      expect(channelSelect().value).toBe(BOOSTING_CHANNEL.id);
      expect(messageArea().value).toBe(editedMessage);
    });
    screen.getByRole('tab', { name: /style/i }).click();
    await waitFor(() => {
      expect(colorInput().value).toBe(editedColor);
    });
    expect(enableSwitch().getAttribute('aria-checked')).toBe('true');
  });

  it('enable FIRST, then select channel, then save (old ordering still works)', async () => {
    stubApiWithStore(GID);
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });

    fireEvent.click(enableSwitch());
    await waitFor(() => {
      expect(patchCalls.length).toBe(1);
    });
    expect(patchCalls[0]).toEqual({ enabled: true });

    fireEvent.change(channelSelect(), { target: { value: BOOSTING_CHANNEL.id } });
    fireEvent.click(saveButton());
    await waitFor(() => {
      expect(patchCalls.length).toBe(2);
    });
    expect(patchCalls[1]).toEqual({ channel_id: BOOSTING_CHANNEL.id });

    cleanup();
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });
    await waitFor(() => {
      expect(channelSelect().value).toBe(BOOSTING_CHANNEL.id);
    });
    expect(enableSwitch().getAttribute('aria-checked')).toBe('true');
  });

  it('backend failure surfaces a sanitized message — never raw Python internals', async () => {
    stubApiWithStore(GID, { patchStatus: 500 });
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });

    fireEvent.change(channelSelect(), { target: { value: BOOSTING_CHANNEL.id } });
    fireEvent.click(saveButton());

    // the sanitized 500 body (what the fixed backend returns) — and
    // absolutely no TypeError / traceback text anywhere in the document
    await waitFor(() => {
      expect(screen.getAllByText(/couldn't complete that/i).length).toBeGreaterThan(0);
    });
    expect(document.body.textContent ?? '').not.toMatch(/TypeError|_EnumValue|Traceback/);
  });

  it('reset (two-click confirm) lands on clean defaults — no dirty leftovers', async () => {
    stubApiWithStore(GID);
    renderBoostersPage(GID);
    await screen.findByRole('heading', { name: 'boosters' });

    // make the page dirty first
    fireEvent.change(channelSelect(), { target: { value: BOOSTING_CHANNEL.id } });
    fireEvent.change(messageArea(), { target: { value: 'custom draft' } });
    expect(screen.getByText('unsaved changes')).toBeTruthy();

    // two-click reset on the milestones tab
    screen.getByRole('tab', { name: /milestones/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/boost milestones/i)).toBeTruthy();
    });
    fireEvent.click(screen.getByRole('button', { name: /reset booster module/i }));
    fireEvent.click(screen.getByRole('button', { name: /click again to reset everything/i }));

    // the reset PATCH carries the full defaults and wipes the server
    // store; the page must land on clean defaults (no preserved dirt)
    await waitFor(() => {
      expect(patchCalls.length).toBe(1);
    });
    expect(patchCalls[0]).toMatchObject({ enabled: false, channel_id: null });
    // the reset button lives on the milestones tab — go back to the
    // announcement tab to inspect the channel/message state
    screen.getByRole('tab', { name: /announcement/i }).click();
    await waitFor(() => {
      expect(screen.getByText(/announcement channel/i)).toBeTruthy();
    });
    await waitFor(() => {
      expect(channelSelect().value).toBe('');
    });
    // the message is back to the page default (starts with the star
    // line), NOT the drafted edit
    expect(messageArea().value).not.toBe('custom draft');
    expect(messageArea().value).toMatch(/a new star is shining brighter/);
    expect(screen.queryByText('unsaved changes')).toBeNull();
  });
});
