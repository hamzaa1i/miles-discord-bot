'use client';

/**
 * lib/supabase.ts — optional Supabase Realtime client.
 *
 * Realtime subscriptions push live updates (new warnings, level-ups,
 * command usage) into the dashboard. This needs:
 *   NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY
 * and the tables added to the supabase_realtime publication:
 *   ALTER PUBLICATION supabase_realtime ADD TABLE public.warnings;
 *   ALTER PUBLICATION supabase_realtime ADD TABLE public.command_usage;
 *   ALTER PUBLICATION supabase_realtime ADD TABLE public.user_levels;
 *
 * When the env vars are missing (or the subscription fails), every
 * consumer silently degrades to periodic refetching.
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js';

let cached: SupabaseClient | null | undefined;

export function getSupabase(): SupabaseClient | null {
  if (cached !== undefined) return cached;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    cached = null;
    return null;
  }
  try {
    cached = createClient(url, key, {
      auth: { persistSession: false, autoRefreshToken: false },
      realtime: { params: { eventsPerSecond: 5 } },
    });
  } catch {
    cached = null;
  }
  return cached;
}

export function supabaseConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}
