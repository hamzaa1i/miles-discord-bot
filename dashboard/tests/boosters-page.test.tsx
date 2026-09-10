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
