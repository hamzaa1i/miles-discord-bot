'use client';

/**
 * useRealtime — subscribe to INSERT events on a Supabase table,
 * filtered to one guild. Fires `onInsert` (and flips `live` true so
 * the UI can show a realtime dot ✧). Degrades to `live: false` when
 * Supabase env vars are missing or the channel errors — consumers
 * should then poll on an interval instead.
 */

import { useEffect, useRef, useState } from 'react';
import { getSupabase } from './supabase';

export function useRealtime(
  guildId: string,
  table: 'warnings' | 'command_usage' | 'user_levels' | 'confessions' | string,
  onInsert?: (row: Record<string, unknown>) => void,
): { live: boolean } {
  const [live, setLive] = useState(false);
  const cbRef = useRef(onInsert);
  cbRef.current = onInsert;

  useEffect(() => {
    const sb = getSupabase();
    if (!sb || !guildId) return;

    const channel = sb
      .channel(`dash:${guildId}:${table}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table, filter: `guild_id=eq.${guildId}` },
        (payload) => {
          cbRef.current?.((payload.new ?? {}) as Record<string, unknown>);
        },
      )
      .subscribe((status) => {
        setLive(status === 'SUBSCRIBED');
      });

    return () => {
      void sb.removeChannel(channel);
      setLive(false);
    };
  }, [guildId, table]);

  return { live };
}
