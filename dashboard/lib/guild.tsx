'use client';

/**
 * lib/guild.tsx — per-guild context: overview + channel/role pickers data.
 * Provided by app/servers/[guildId]/layout.tsx so every module page
 * can read guild metadata and render ChannelPicker/RolePicker without
 * re-fetching.
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { endpoints, ApiRequestError } from './api';
import type { GuildOverview, GuildResources, AuditEntry } from './types';

interface GuildState {
  guildId: string;
  overview: GuildOverview | null;
  resources: GuildResources | null;
  audit: AuditEntry[];
  loading: boolean;
  error: string | null;
  reloadOverview: () => Promise<void>;
  reloadAudit: () => Promise<void>;
}

const GuildContext = createContext<GuildState>({
  guildId: '',
  overview: null,
  resources: null,
  audit: [],
  loading: true,
  error: null,
  reloadOverview: async () => {},
  reloadAudit: async () => {},
});

export function GuildProvider({ guildId, children }: { guildId: string; children: React.ReactNode }) {
  const [overview, setOverview] = useState<GuildOverview | null>(null);
  const [resources, setResources] = useState<GuildResources | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reloadOverview = useCallback(async () => {
    try {
      setOverview(await endpoints.overview(guildId));
      setError(null);
    } catch (e) {
      if (e instanceof ApiRequestError) setError(e.message);
      else if (e instanceof Error) setError(e.message);
    }
  }, [guildId]);

  const reloadAudit = useCallback(async () => {
    try {
      const res = await endpoints.audit(guildId);
      setAudit(res.entries ?? []);
    } catch {
      // audit is best-effort
    }
  }, [guildId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [ov, res] = await Promise.all([
          endpoints.overview(guildId),
          endpoints.resources(guildId),
        ]);
        if (cancelled) return;
        setOverview(ov);
        setResources(res);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'could not load this server');
      } finally {
        if (!cancelled) setLoading(false);
      }
      void reloadAudit();
    })();
    return () => {
      cancelled = true;
    };
  }, [guildId, reloadAudit]);

  return (
    <GuildContext.Provider
      value={{ guildId, overview, resources, audit, loading, error, reloadOverview, reloadAudit }}
    >
      {children}
    </GuildContext.Provider>
  );
}

export function useGuild() {
  return useContext(GuildContext);
}
