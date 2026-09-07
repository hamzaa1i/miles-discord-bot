# dashboard/DEVELOPMENT.md — contributing guide

thanks for wanting to make the veloura softer ✦

## getting set up

```bash
git clone https://github.com/hamzaa1i/miles-discord-bot
cd miles-discord-bot/dashboard
npm install
cp .env.example .env.local   # see README.md for the values
npm run dev
```

You'll also want the bot's Flask API reachable (`python main.py` at the repo
root, or point `NEXT_PUBLIC_API_URL` at the Render deployment — though its
CORS only accepts configured dashboard origins, the proxy runs server-side
so CORS doesn't apply).

## conventions

- **typescript strict** — `npm run build` type-checks; don't ship `any`.
- **'use client'** on every component that touches hooks; keep pages as
  thin client components under `app/servers/[guildId]/<module>/page.tsx`.
- **no new runtime dependencies** without a strong reason — charts,
  pickers, toasts and tabs are all hand-rolled on purpose (see
  ARCHITECTURE.md).
- **veloura palette** lives in `tailwind.config.ts` — use the
  `veloura-*` classes and the `.veloura-*` component classes in
  `styles/globals.css`, not raw hex values.
- lowercase aesthetic for UI copy; emoji sparingly: ✦ ♡ ✧ ✩ 🌙.

## adding a module page

1. **If the module has settings in one table**, add an entry to
   `lib/modules.ts` → `MODULES` (slug, route, title, icon, `settings`,
   `fields`, optional `defaults`).
2. Create `app/servers/[guildId]/<route>/page.tsx`:

   ```tsx
   'use client';
   import { useParams } from 'next/navigation';
   import { SettingsForm } from '@/components/SettingsForm';
   import { MODULES } from '@/lib/modules';

   export default function Page() {
     const params = useParams<{ guildId: string }>();
     return <SettingsForm gid={String(params.guildId)} module={MODULES.yourModule} />;
   }
   ```

3. Add it to the sidebar in `lib/modules.ts` → `SIDEBAR`.
4. If the table is new, add it to `_TABLE_COLUMNS` in `utils/db.py` and the
   `DASHBOARD_MODULES` registry in `utils/dashboard_api.py` (plus defaults).

**Rich page?** Copy the pattern of `welcome/page.tsx` or `qotd/page.tsx`:
`useModuleSettings` + `ModuleCard` + `SaveBar`, pickers from
`components/`, actions via `endpoints.action()`.

## adding a live action (bot-side)

1. Executor case in `utils/dashboard_actions.py` → `execute_dashboard_action`
   (return `{"ok": bool, "detail": str}`, never raise).
2. Allow-list the action name in `utils/dashboard_api.py` → `VALID_ACTIONS`
   (or `OWNER_ACTIONS` + a POST /owner/<action> route for owner-only).
3. Trigger it from a page with `endpoints.action(gid, 'action_name', params)`.
4. The bot executes within ~5s; surface that in your toast copy.

## testing

```bash
# backend (52 assertions, no discord/supabase needed — mocked)
python scripts/test_dashboard_api.py

# live backend + curl cheatsheet
python scripts/test_dashboard_api.py --serve   # boots :8081 with fakes

# frontend
npm run build     # types + bundling
npm run lint
```

When you touch `utils/dashboard_api.py` or `utils/dashboard_actions.py`,
run the backend suite and `python -m py_compile` on both.

## gotchas

- The Flask API runs in a **separate thread** from the bot's event loop —
  never call bot coroutines directly from a route; enqueue an action.
- `get_guild_setting` is cached ~60s — writes through the dashboard
  invalidate it, but external DB edits need the `purge_cache` action.
- Supabase realtime needs the table in the `supabase_realtime`
  publication, or it silently no-ops (by design).
- Discord OAuth redirect URIs are **exact strings** — localhost and
  production are two separate entries.
